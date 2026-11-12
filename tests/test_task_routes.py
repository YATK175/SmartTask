
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app import create_app
from app.extensions import db
from app.models import Task, User
from app.routes import task_routes


class TestConfig:
    TESTING = True
    SECRET_KEY = "task-routes-test-secret"

    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SQLALCHEMY_ENGINE_OPTIONS = {
        "connect_args": {
            "check_same_thread": False
        }
    }


@pytest.fixture
def app():
    """Створює ізольований Flask-застосунок і тестову БД."""

    application = create_app(TestConfig)

    try:
        with application.app_context():
            db.drop_all()
            db.create_all()

        yield application

    finally:
        with application.app_context():
            db.session.remove()

            try:
                db.drop_all()
            finally:
                db.engine.dispose()


@pytest.fixture
def authenticated_client(app):
    """Створює тестового користувача та авторизований клієнт."""

    user_id = create_user(
        app,
        username="task_tester",
        email="task@example.com",
    )

    client = app.test_client()

    response = client.post(
        "/api/auth/login",
        json={
            "email": "task@example.com",
            "password": "TestPassword123",
        },
    )

    assert response.status_code == 200

    return client, user_id


def create_user(app, username, email):
    """Створює тестового користувача."""

    with app.app_context():
        user = User(
            username=username,
            email=email,
        )

        user.set_password("TestPassword123")

        db.session.add(user)
        db.session.commit()

        return user.id


def create_task(app, user_id, title="Test task", priority="HIGH"):
    """Створює завдання безпосередньо в тестовій БД."""

    with app.app_context():
        task = Task(
            user_id=user_id,
            title=title,
            priority=priority,
            status="NEW",
            deadline=(
                datetime.now(timezone.utc).replace(tzinfo=None)
                + timedelta(days=3)
            ),
            estimated_duration_minutes=60,
        )

        db.session.add(task)
        db.session.commit()

        return task.id


def task_payload(title="Test task", priority="HIGH"):
    """Формує коректні дані для створення завдання."""

    return {
        "title": title,
        "description": "Test description",
        "priority": priority,
        "deadline": (
            datetime.now(timezone.utc) + timedelta(days=3)
        ).isoformat(),
        "estimated_duration_minutes": 60,
    }


def test_task_routes_require_authentication(app):
    """Перевіряє захист основних маршрутів від неавторизованого доступу."""

    client = app.test_client()

    responses = [
        client.get("/api/tasks"),
        client.post(
            "/api/tasks",
            json=task_payload(),
        ),
        client.get("/api/tasks/1"),
        client.patch(
            "/api/tasks/1",
            json={"title": "Updated"},
        ),
        client.delete("/api/tasks/1"),
        client.post(
            "/api/tasks/1/complete",
            json={},
        ),
    ]

    assert all(response.status_code == 401 for response in responses)


def test_create_task_success(authenticated_client):
    """Перевіряє успішне створення завдання."""

    client, user_id = authenticated_client

    response = client.post(
        "/api/tasks",
        json=task_payload(
            title="Prepare project report",
            priority="HIGH",
        ),
    )

    assert response.status_code == 201

    result = response.get_json()
    task = result["task"]

    assert task["title"] == "Prepare project report"
    assert task["priority"] == "HIGH"
    assert task["status"] == "NEW"
    assert task["estimated_duration_minutes"] == 60
    assert task["user_id"] == user_id


def test_create_task_rejects_invalid_json(authenticated_client):
    """Перевіряє відхилення некоректного JSON."""

    client, _ = authenticated_client

    response = client.post(
        "/api/tasks",
        data="{invalid json",
        content_type="application/json",
    )

    assert response.status_code == 400
    assert "error" in response.get_json()


def test_create_task_rejects_invalid_data(authenticated_client):
    """Перевіряє валідацію обов'язкових полів завдання."""

    client, _ = authenticated_client

    payload = task_payload(title="   ")

    response = client.post(
        "/api/tasks",
        json=payload,
    )

    assert response.status_code == 400
    assert "error" in response.get_json()


def test_get_tasks_returns_only_current_users_tasks(
    app,
    authenticated_client,
):
    """Перевіряє отримання списку завдань із ізоляцією користувачів."""

    client, user_id = authenticated_client

    first_response = client.post(
        "/api/tasks",
        json=task_payload(
            title="High priority report",
            priority="HIGH",
        ),
    )

    assert first_response.status_code == 201

    client.post(
        "/api/tasks",
        json=task_payload(
            title="Low priority report",
            priority="LOW",
        ),
    )

    other_user_id = create_user(
        app,
        username="another_user",
        email="another@example.com",
    )

    create_task(
        app,
        other_user_id,
        title="Foreign task",
        priority="HIGH",
    )

    response = client.get("/api/tasks?priority=HIGH")

    assert response.status_code == 200

    result = response.get_json()

    assert result["count"] == 1
    assert len(result["tasks"]) == 1
    assert result["tasks"][0]["title"] == "High priority report"
    assert result["tasks"][0]["user_id"] == user_id


@pytest.mark.parametrize(
    "query",
    [
        "?status=UNKNOWN",
        "?priority=URGENT",
        "?sort_by=unknown_field",
        "?descending=maybe",
        "?category_id=abc",
    ],
)
def test_get_tasks_rejects_invalid_filters(
    authenticated_client,
    query,
):
    """Перевіряє валідацію параметрів фільтрації."""

    client, _ = authenticated_client

    response = client.get(f"/api/tasks{query}")

    assert response.status_code == 400
    assert "error" in response.get_json()


def test_get_task_success_and_foreign_task_is_hidden(
    app,
    authenticated_client,
):
    """Перевіряє отримання власного та недоступність чужого завдання."""

    client, _ = authenticated_client

    own_response = client.post(
        "/api/tasks",
        json=task_payload(title="My task"),
    )

    task_id = own_response.get_json()["task"]["id"]

    response = client.get(f"/api/tasks/{task_id}")

    assert response.status_code == 200
    assert response.get_json()["task"]["title"] == "My task"

    other_user_id = create_user(
        app,
        username="foreign_user",
        email="foreign@example.com",
    )

    foreign_task_id = create_task(
        app,
        other_user_id,
        title="Foreign task",
    )

    foreign_response = client.get(
        f"/api/tasks/{foreign_task_id}"
    )

    assert foreign_response.status_code == 404


def test_update_task_success_without_previous_prediction(
    authenticated_client,
):
    """Перевіряє оновлення завдання без попереднього ML-прогнозу."""

    client, _ = authenticated_client

    create_response = client.post(
        "/api/tasks",
        json=task_payload(),
    )

    task_id = create_response.get_json()["task"]["id"]

    response = client.patch(
        f"/api/tasks/{task_id}",
        json={
            "title": "Updated task",
            "estimated_duration_minutes": 90,
        },
    )

    assert response.status_code == 200

    result = response.get_json()

    assert result["task"]["title"] == "Updated task"
    assert result["task"]["estimated_duration_minutes"] == 90
    assert result["prediction_refresh"] is None


@pytest.mark.parametrize(
    "payload",
    [
        {"priority": "URGENT"},
        {"unknown_field": "value"},
        {"estimated_duration_minutes": -10},
    ],
)
def test_update_task_rejects_invalid_data(
    authenticated_client,
    payload,
):
    """Перевіряє відхилення некоректних даних під час редагування."""

    client, _ = authenticated_client

    create_response = client.post(
        "/api/tasks",
        json=task_payload(),
    )

    task_id = create_response.get_json()["task"]["id"]

    response = client.patch(
        f"/api/tasks/{task_id}",
        json=payload,
    )

    assert response.status_code == 400
    assert "error" in response.get_json()


def test_update_task_rejects_invalid_json(authenticated_client):
    """Перевіряє відхилення некоректного JSON під час редагування."""

    client, _ = authenticated_client

    create_response = client.post(
        "/api/tasks",
        json=task_payload(),
    )

    task_id = create_response.get_json()["task"]["id"]

    response = client.patch(
        f"/api/tasks/{task_id}",
        data="{invalid json",
        content_type="application/json",
    )

    assert response.status_code == 400


def test_update_task_automatically_refreshes_prediction(
    authenticated_client,
    monkeypatch,
):
    """Перевіряє автоматичний перерахунок попереднього ML-прогнозу."""

    client, _ = authenticated_client

    create_response = client.post(
        "/api/tasks",
        json=task_payload(),
    )

    task_id = create_response.get_json()["task"]["id"]

    monkeypatch.setattr(
        task_routes.prediction_service,
        "get_latest_prediction",
        lambda user_id, task_id: object(),
    )

    fake_prediction = SimpleNamespace(
        risk_score=0.15,
        risk_level="LOW",
        source="ML",
        model_version="test-model",
    )

    monkeypatch.setattr(
        task_routes.prediction_service,
        "predict_task",
        lambda user_id, task_id: {
            "prediction": fake_prediction,
        },
    )

    response = client.patch(
        f"/api/tasks/{task_id}",
        json={"estimated_duration_minutes": 90},
    )

    assert response.status_code == 200

    result = response.get_json()

    assert result["task"]["estimated_duration_minutes"] == 90

    assert result["prediction_refresh"]["status"] == "updated"
    assert result["prediction_refresh"]["risk_score"] == 0.15
    assert result["prediction_refresh"]["risk_level"] == "LOW"
    assert result["prediction_refresh"]["source"] == "ML"
    assert result["prediction_refresh"]["model_version"] == "test-model"


def test_update_task_refresh_failure_does_not_undo_update(
    authenticated_client,
    monkeypatch,
):
    """Перевіряє збереження завдання, якщо повторний прогноз не вдався."""

    client, _ = authenticated_client

    create_response = client.post(
        "/api/tasks",
        json=task_payload(),
    )

    task_id = create_response.get_json()["task"]["id"]

    monkeypatch.setattr(
        task_routes.prediction_service,
        "get_latest_prediction",
        lambda user_id, task_id: object(),
    )

    def fail_prediction(user_id, task_id):
        raise RuntimeError("Test prediction error")

    monkeypatch.setattr(
        task_routes.prediction_service,
        "predict_task",
        fail_prediction,
    )

    response = client.patch(
        f"/api/tasks/{task_id}",
        json={"estimated_duration_minutes": 90},
    )

    assert response.status_code == 200

    result = response.get_json()

    assert result["task"]["estimated_duration_minutes"] == 90
    assert result["prediction_refresh"]["status"] == "failed"


def test_update_task_does_not_refresh_completed_task(
    authenticated_client,
    monkeypatch,
):
    """Перевіряє, що завершене завдання не запускає новий прогноз."""

    client, _ = authenticated_client

    create_response = client.post(
        "/api/tasks",
        json=task_payload(),
    )

    task_id = create_response.get_json()["task"]["id"]

    complete_response = client.post(
        f"/api/tasks/{task_id}/complete",
        json={"actual_duration_minutes": 60},
    )

    assert complete_response.status_code == 200

    monkeypatch.setattr(
        task_routes.prediction_service,
        "get_latest_prediction",
        lambda user_id, task_id: object(),
    )

    def unexpected_prediction(user_id, task_id):
        raise AssertionError("Prediction should not run for completed task")

    monkeypatch.setattr(
        task_routes.prediction_service,
        "predict_task",
        unexpected_prediction,
    )

    response = client.patch(
        f"/api/tasks/{task_id}",
        json={"estimated_duration_minutes": 90},
    )

    assert response.status_code == 200
    assert response.get_json()["prediction_refresh"] is None


def test_update_foreign_task_returns_404(
    app,
    authenticated_client,
):
    """Перевіряє заборону редагування чужого завдання."""

    client, _ = authenticated_client

    other_user_id = create_user(
        app,
        username="foreign_editor",
        email="foreign_editor@example.com",
    )

    task_id = create_task(app, other_user_id)

    response = client.patch(
        f"/api/tasks/{task_id}",
        json={"title": "Unauthorized update"},
    )

    assert response.status_code == 404


def test_delete_task_success_and_missing(
    authenticated_client,
):
    """Перевіряє видалення завдання та відповідь для відсутнього запису."""

    client, _ = authenticated_client

    create_response = client.post(
        "/api/tasks",
        json=task_payload(),
    )

    task_id = create_response.get_json()["task"]["id"]

    response = client.delete(f"/api/tasks/{task_id}")

    assert response.status_code == 200

    missing_response = client.get(
        f"/api/tasks/{task_id}"
    )

    assert missing_response.status_code == 404


def test_delete_foreign_task_returns_404(
    app,
    authenticated_client,
):
    """Перевіряє заборону видалення чужого завдання."""

    client, _ = authenticated_client

    other_user_id = create_user(
        app,
        username="foreign_deleter",
        email="foreign_deleter@example.com",
    )

    task_id = create_task(app, other_user_id)

    response = client.delete(
        f"/api/tasks/{task_id}"
    )

    assert response.status_code == 404


def test_complete_task_success(authenticated_client):
    """Перевіряє успішне завершення завдання."""

    client, _ = authenticated_client

    create_response = client.post(
        "/api/tasks",
        json=task_payload(),
    )

    task_id = create_response.get_json()["task"]["id"]

    response = client.post(
        f"/api/tasks/{task_id}/complete",
        json={"actual_duration_minutes": 75},
    )

    assert response.status_code == 200

    task = response.get_json()["task"]

    assert task["status"] == "COMPLETED"
    assert task["actual_duration_minutes"] == 75
    assert task["completed_at"] is not None


@pytest.mark.parametrize(
    "duration",
    [-1, True, "invalid"],
)
def test_complete_task_rejects_invalid_duration(
    authenticated_client,
    duration,
):
    """Перевіряє валідацію фактичної тривалості."""

    client, _ = authenticated_client

    create_response = client.post(
        "/api/tasks",
        json=task_payload(),
    )

    task_id = create_response.get_json()["task"]["id"]

    response = client.post(
        f"/api/tasks/{task_id}/complete",
        json={"actual_duration_minutes": duration},
    )

    assert response.status_code == 400
    assert "error" in response.get_json()


def test_complete_task_returns_404_for_missing_task(
    authenticated_client,
):
    """Перевіряє завершення неіснуючого завдання."""

    client, _ = authenticated_client

    response = client.post(
        "/api/tasks/99999/complete",
        json={"actual_duration_minutes": 60},
    )

    assert response.status_code == 404
