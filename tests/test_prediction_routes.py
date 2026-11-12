
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app import create_app
from app.extensions import db
from app.models import User, Task, Prediction
from app.routes import prediction_routes
from app.services import TaskNotFoundError


class TestConfig:
    TESTING = True
    SECRET_KEY = "prediction-routes-test-secret"

    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SQLALCHEMY_ENGINE_OPTIONS = {
        "connect_args": {"check_same_thread": False}
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


def create_task(app, user_id, title="Prediction test task"):
    """Створює активне тестове завдання."""

    with app.app_context():
        task = Task(
            user_id=user_id,
            title=title,
            description="Test description",
            priority="HIGH",
            status="NEW",
            deadline=(
                datetime.now(timezone.utc).replace(tzinfo=None)
                + timedelta(days=3)
            ),
            estimated_duration_minutes=120,
        )

        db.session.add(task)
        db.session.commit()

        return task.id


def create_prediction(app, task_id, risk_score=0.25):
    """Зберігає тестовий прогноз у базі даних."""

    with app.app_context():
        prediction = Prediction(
            task_id=task_id,
            risk_score=risk_score,
            risk_level="LOW",
            source="ML",
            model_version="rf-synthetic-v2",
        )

        prediction.set_features({
            "features": {
                "priority_level": 3,
                "days_until_deadline": 3.0,
                "estimated_duration_hours": 2.0,
                "active_tasks_count": 1,
                "on_time_completion_rate": 0.625,
                "task_age_days": 0.5,
            },
            "classification_threshold": 0.2575,
            "is_at_risk": False,
            "dataset_type": "synthetic",
        })

        db.session.add(prediction)
        db.session.commit()

        return prediction.id


@pytest.fixture
def authenticated_client(app):
    """Створює авторизованого користувача."""

    user_id = create_user(
        app,
        "prediction_tester",
        "prediction@example.com",
    )

    task_id = create_task(app, user_id)

    client = app.test_client()

    response = client.post(
        "/api/auth/login",
        json={
            "email": "prediction@example.com",
            "password": "TestPassword123",
        },
    )

    assert response.status_code == 200

    return client, user_id, task_id


def make_fake_prediction(task_id):
    """Створює об'єкт прогнозу для ізольованого тесту маршруту."""

    snapshot = {
        "features": {
            "priority_level": 3,
            "days_until_deadline": 3.0,
            "estimated_duration_hours": 2.0,
        },
        "classification_threshold": 0.2575,
        "is_at_risk": False,
        "dataset_type": "synthetic",
    }

    return SimpleNamespace(
        id=100,
        task_id=task_id,
        risk_score=0.18,
        risk_level="LOW",
        source="ML",
        model_version="rf-synthetic-v2",
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        get_features=lambda: snapshot,
    )


def test_prediction_routes_require_authentication(app):
    """Перевіряє авторизацію для всіх маршрутів прогнозування."""

    client = app.test_client()

    responses = [
        client.post("/api/predictions/tasks/1"),
        client.get("/api/predictions/tasks/1"),
        client.get("/api/predictions/tasks/1/latest"),
    ]

    assert all(
        response.status_code == 401
        for response in responses
    )


def test_predict_task_success(
    authenticated_client,
    monkeypatch,
):
    """Перевіряє успішне створення прогнозу через API."""

    client, user_id, task_id = authenticated_client

    fake_prediction = make_fake_prediction(task_id)
    received_arguments = []

    def fake_predict_task(received_user_id, received_task_id):
        received_arguments.append(
            (received_user_id, received_task_id)
        )

        return {
            "prediction": fake_prediction,
            "analysis": {
                "risk_level": "LOW",
                "recommendations": [
                    "Continue working according to the plan."
                ],
            },
        }

    monkeypatch.setattr(
        prediction_routes.prediction_service,
        "predict_task",
        fake_predict_task,
    )

    response = client.post(
        f"/api/predictions/tasks/{task_id}"
    )

    assert response.status_code == 201

    result = response.get_json()

    assert result["prediction"]["id"] == 100
    assert result["prediction"]["task_id"] == task_id
    assert result["prediction"]["risk_score"] == 0.18
    assert result["prediction"]["risk_percentage"] == 18.0
    assert result["prediction"]["risk_level"] == "LOW"
    assert result["prediction"]["source"] == "ML"
    assert result["prediction"]["model_version"] == "rf-synthetic-v2"

    assert result["analysis"]["risk_level"] == "LOW"

    assert received_arguments == [(user_id, task_id)]


def test_predict_task_returns_404_for_missing_task(
    authenticated_client,
    monkeypatch,
):
    """Перевіряє обробку відсутнього або недоступного завдання."""

    client, _, task_id = authenticated_client

    def missing_task(user_id, received_task_id):
        raise TaskNotFoundError("Task not found")

    monkeypatch.setattr(
        prediction_routes.prediction_service,
        "predict_task",
        missing_task,
    )

    response = client.post(
        f"/api/predictions/tasks/{task_id}"
    )

    assert response.status_code == 404
    assert "error" in response.get_json()


def test_predict_task_returns_400_for_value_error(
    authenticated_client,
    monkeypatch,
):
    """Перевіряє обробку помилки бізнес-логіки прогнозування."""

    client, _, task_id = authenticated_client

    def invalid_prediction(user_id, received_task_id):
        raise ValueError("Task cannot be predicted")

    monkeypatch.setattr(
        prediction_routes.prediction_service,
        "predict_task",
        invalid_prediction,
    )

    response = client.post(
        f"/api/predictions/tasks/{task_id}"
    )

    assert response.status_code == 400
    assert "error" in response.get_json()


def test_predict_foreign_task_returns_404(
    app,
    authenticated_client,
    monkeypatch,
):
    """Перевіряє, що прогноз не запускається для чужого завдання."""

    client, _, _ = authenticated_client

    other_user_id = create_user(
        app,
        "foreign_prediction_user",
        "foreign_prediction@example.com",
    )

    foreign_task_id = create_task(
        app,
        other_user_id,
        "Foreign task",
    )

    def reject_foreign_task(user_id, task_id):
        assert user_id != other_user_id
        raise TaskNotFoundError("Task not found")

    monkeypatch.setattr(
        prediction_routes.prediction_service,
        "predict_task",
        reject_foreign_task,
    )

    response = client.post(
        f"/api/predictions/tasks/{foreign_task_id}"
    )

    assert response.status_code == 404


def test_get_prediction_history_success(
    app,
    authenticated_client,
):
    """Перевіряє отримання історії прогнозів."""

    client, user_id, task_id = authenticated_client

    create_prediction(app, task_id, risk_score=0.20)
    create_prediction(app, task_id, risk_score=0.35)

    response = client.get(
        f"/api/predictions/tasks/{task_id}"
    )

    assert response.status_code == 200

    result = response.get_json()

    assert result["task_id"] == task_id
    assert result["count"] == 2
    assert len(result["predictions"]) == 2

    assert all(
        prediction["task_id"] == task_id
        for prediction in result["predictions"]
    )

    assert all(
        prediction["source"] == "ML"
        for prediction in result["predictions"]
    )


def test_get_empty_prediction_history(
    authenticated_client,
):
    """Перевіряє історію завдання без прогнозів."""

    client, _, task_id = authenticated_client

    response = client.get(
        f"/api/predictions/tasks/{task_id}"
    )

    assert response.status_code == 200

    result = response.get_json()

    assert result["task_id"] == task_id
    assert result["count"] == 0
    assert result["predictions"] == []


def test_get_prediction_history_returns_404_for_missing_task(
    authenticated_client,
):
    """Перевіряє отримання історії неіснуючого завдання."""

    client, _, _ = authenticated_client

    response = client.get(
        "/api/predictions/tasks/99999"
    )

    assert response.status_code == 404
    assert "error" in response.get_json()


def test_get_foreign_prediction_history_returns_404(
    app,
    authenticated_client,
):
    """Перевіряє заборону перегляду історії чужого завдання."""

    client, _, _ = authenticated_client

    other_user_id = create_user(
        app,
        "foreign_history_user",
        "foreign_history@example.com",
    )

    foreign_task_id = create_task(
        app,
        other_user_id,
        "Foreign history task",
    )

    create_prediction(app, foreign_task_id)

    response = client.get(
        f"/api/predictions/tasks/{foreign_task_id}"
    )

    assert response.status_code == 404


def test_get_latest_prediction_success(
    app,
    authenticated_client,
):
    """Перевіряє отримання останнього прогнозу."""

    client, _, task_id = authenticated_client

    create_prediction(app, task_id, risk_score=0.20)
    latest_id = create_prediction(
        app,
        task_id,
        risk_score=0.35,
    )

    response = client.get(
        f"/api/predictions/tasks/{task_id}/latest"
    )

    assert response.status_code == 200

    result = response.get_json()
    prediction = result["prediction"]

    assert prediction["id"] == latest_id
    assert prediction["task_id"] == task_id
    assert prediction["risk_score"] == 0.35
    assert prediction["risk_percentage"] == 35.0
    assert prediction["risk_level"] == "LOW"
    assert prediction["source"] == "ML"
    assert prediction["model_version"] == "rf-synthetic-v2"


def test_get_latest_prediction_returns_404_when_empty(
    authenticated_client,
):
    """Перевіряє ситуацію, коли прогнозів ще немає."""

    client, _, task_id = authenticated_client

    response = client.get(
        f"/api/predictions/tasks/{task_id}/latest"
    )

    assert response.status_code == 404

    result = response.get_json()

    assert "error" in result


def test_get_latest_prediction_returns_404_for_missing_task(
    authenticated_client,
):
    """Перевіряє отримання прогнозу неіснуючого завдання."""

    client, _, _ = authenticated_client

    response = client.get(
        "/api/predictions/tasks/99999/latest"
    )

    assert response.status_code == 404
    assert "error" in response.get_json()


def test_get_foreign_latest_prediction_returns_404(
    app,
    authenticated_client,
):
    """Перевіряє заборону отримання чужого прогнозу."""

    client, _, _ = authenticated_client

    other_user_id = create_user(
        app,
        "foreign_latest_user",
        "foreign_latest@example.com",
    )

    foreign_task_id = create_task(
        app,
        other_user_id,
        "Foreign latest task",
    )

    create_prediction(app, foreign_task_id)

    response = client.get(
        f"/api/predictions/tasks/{foreign_task_id}/latest"
    )

    assert response.status_code == 404
