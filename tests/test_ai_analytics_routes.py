
import json

from datetime import datetime, timedelta, timezone

import pytest

from app import create_app
from app.extensions import db
from app.models import User, Task, Prediction
from app.routes import ai_analytics_routes


class TestConfig:
    """Ізольована конфігурація тестового застосунку."""

    TESTING = True
    SECRET_KEY = "ai-analytics-test-secret"

    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SQLALCHEMY_ENGINE_OPTIONS = {
        "connect_args": {
            "check_same_thread": False
        }
    }


@pytest.fixture
def app():
    """Створює тимчасову базу для тестування API."""

    application = create_app(TestConfig)

    with application.app_context():
        db.drop_all()
        db.create_all()

    yield application

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
            email=email
        )

        user.set_password("TestPassword123")

        db.session.add(user)
        db.session.commit()

        return user.id


def login_user(client, email):
    """Авторизує тестового користувача через API."""

    response = client.post(
        "/api/auth/login",
        json={
            "email": email,
            "password": "TestPassword123"
        }
    )

    assert response.status_code == 200

    return response


def create_task(app, user_id, title):
    """Створює тестове завдання."""

    with app.app_context():
        task = Task(
            user_id=user_id,
            title=title,
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


def create_prediction(
    app,
    task_id,
    risk_score,
    risk_level,
    is_at_risk
):
    """Створює тестовий запис прогнозу."""

    with app.app_context():
        prediction = Prediction(
            task_id=task_id,
            risk_score=risk_score,
            risk_level=risk_level,
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
            "is_at_risk": is_at_risk,
            "dataset_type": "synthetic",
        })

        db.session.add(prediction)
        db.session.commit()

        return prediction.id


def test_ai_summary_requires_authentication(app):
    """Перевіряє захист AI Analytics."""

    client = app.test_client()

    response = client.get(
        "/api/ai-analytics/summary"
    )

    assert response.status_code == 401


def test_ai_summary_counts_latest_predictions_of_user(app):
    """
    Перевіряє статистику, останні прогнози
    та ізоляцію даних між користувачами.
    """

    user_id = create_user(
        app,
        "analytics_user",
        "analytics@example.com"
    )

    other_user_id = create_user(
        app,
        "other_user",
        "other@example.com"
    )

    # Завдання першого користувача.
    task_one = create_task(
        app,
        user_id,
        "Перше завдання"
    )

    task_two = create_task(
        app,
        user_id,
        "Друге завдання"
    )

    # Завдання іншого користувача.
    other_task = create_task(
        app,
        other_user_id,
        "Чуже завдання"
    )

    # Два прогнози одного завдання.
    # В аналітиці повинен враховуватися лише останній.
    create_prediction(
        app,
        task_one,
        0.20,
        "LOW",
        False
    )

    create_prediction(
        app,
        task_one,
        0.75,
        "HIGH",
        True
    )

    # Чужий прогноз не повинен потрапити до статистики.
    create_prediction(
        app,
        other_task,
        0.90,
        "HIGH",
        True
    )

    client = app.test_client()

    login_user(
        client,
        "analytics@example.com"
    )

    response = client.get(
        "/api/ai-analytics/summary"
    )

    assert response.status_code == 200

    result = response.get_json()

    summary = result["summary"]

    assert summary["total_tasks"] == 2
    assert summary["analyzed_tasks"] == 1
    assert summary["unanalyzed_tasks"] == 1

    # Перевіряємо лише останній прогноз task_one.
    assert summary["low_risk"] == 0
    assert summary["medium_risk"] == 0
    assert summary["high_risk"] == 1

    # Чуже завдання не повинно повертатися.
    returned_ids = {
        task["id"]
        for task in result["tasks"]
    }

    assert returned_ids == {task_one, task_two}

    latest_prediction = next(
        task["latest_prediction"]
        for task in result["tasks"]
        if task["id"] == task_one
    )

    assert latest_prediction["risk_level"] == "HIGH"
    assert latest_prediction["risk_percentage"] == 75.0
    assert latest_prediction["is_at_risk"] is True


def test_model_metrics_endpoint(app, tmp_path, monkeypatch):
    """Перевіряє повернення метрик Random Forest."""

    metrics = {
        "model_version": "rf-synthetic-v2",
        "dataset_type": "synthetic",
        "accuracy": 0.605,
        "precision": 0.3254,
        "recall": 0.8107,
        "f1_score": 0.4644,
        "roc_auc": 0.7402,
    }

    metrics_file = tmp_path / "metrics.json"

    metrics_file.write_text(
        json.dumps(metrics),
        encoding="utf-8"
    )

    monkeypatch.setattr(
        ai_analytics_routes,
        "METRICS_PATH",
        metrics_file
    )

    user_id = create_user(
        app,
        "metrics_user",
        "metrics@example.com"
    )

    client = app.test_client()

    login_user(
        client,
        "metrics@example.com"
    )

    response = client.get(
        "/api/ai-analytics/model-metrics"
    )

    assert response.status_code == 200

    result = response.get_json()

    assert result["model_version"] == "rf-synthetic-v2"
    assert result["dataset_type"] == "synthetic"
    assert result["accuracy"] == 0.605
    assert result["recall"] == 0.8107


def test_model_metrics_missing_file(app, tmp_path, monkeypatch):
    """Перевіряє обробку відсутнього файлу метрик."""

    metrics_file = tmp_path / "missing_metrics.json"

    monkeypatch.setattr(
        ai_analytics_routes,
        "METRICS_PATH",
        metrics_file
    )

    user_id = create_user(
        app,
        "missing_user",
        "missing@example.com"
    )

    client = app.test_client()

    login_user(
        client,
        "missing@example.com"
    )

    response = client.get(
        "/api/ai-analytics/model-metrics"
    )

    assert response.status_code == 404

    assert "error" in response.get_json()


def test_model_metrics_invalid_json(app, tmp_path, monkeypatch):
    """Перевіряє обробку пошкодженого JSON-файлу."""

    metrics_file = tmp_path / "invalid_metrics.json"

    metrics_file.write_text(
        "{invalid json",
        encoding="utf-8"
    )

    monkeypatch.setattr(
        ai_analytics_routes,
        "METRICS_PATH",
        metrics_file
    )

    user_id = create_user(
        app,
        "invalid_user",
        "invalid@example.com"
    )

    client = app.test_client()

    login_user(
        client,
        "invalid@example.com"
    )

    response = client.get(
        "/api/ai-analytics/model-metrics"
    )

    assert response.status_code == 500

    assert "error" in response.get_json()
