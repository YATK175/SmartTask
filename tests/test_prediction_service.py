
from datetime import datetime, timedelta, timezone

import pytest

from app import create_app
from app.extensions import db
from app.models import User, Task, Prediction
from app.services import PredictionService, TaskNotFoundError


class TestConfig:
    TESTING = True
    SECRET_KEY = "prediction-test-secret"

    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SQLALCHEMY_ENGINE_OPTIONS = {
        "connect_args": {
            "check_same_thread": False
        }
    }


@pytest.fixture
def prediction_context():
    """Створює ізольовану тестову БД та тестове завдання."""

    app = create_app(TestConfig)

    with app.app_context():
        db.create_all()

        user = User(
            username="prediction_user",
            email="prediction@example.com"
        )

        user.set_password("TestPassword123")

        db.session.add(user)
        db.session.flush()

        task = Task(
            user_id=user.id,
            title="Перевірка прогнозування",
            description="Тест ML-інтеграції",
            priority="HIGH",
            status="NEW",
            deadline=(
                datetime.now(timezone.utc).replace(tzinfo=None)
                + timedelta(days=2)
            ),
            estimated_duration_minutes=180,
        )

        db.session.add(task)
        db.session.commit()

        user_id = user.id
        task_id = task.id

        yield user_id, task_id

        db.session.remove()

        try:
            db.drop_all()
        finally:
            db.engine.dispose()


def test_prediction_is_saved(prediction_context):
    """Перевіряє створення прогнозу та запис у БД."""

    user_id, task_id = prediction_context

    service = PredictionService()

    result = service.predict_task(
        user_id,
        task_id
    )

    prediction = result["prediction"]
    analysis = result["analysis"]

    assert prediction.id is not None

    assert prediction.task_id == task_id

    assert prediction.source == "ML"

    assert prediction.model_version == "rf-synthetic-v2"

    assert 0 <= prediction.risk_score <= 1

    assert prediction.risk_level in {
        "LOW",
        "MEDIUM",
        "HIGH"
    }

    assert len(analysis["recommendations"]) > 0

    saved = db.session.get(Prediction, prediction.id)

    assert saved is not None

    snapshot = saved.get_features()

    assert "features" in snapshot

    assert "classification_threshold" in snapshot

    assert "is_at_risk" in snapshot


def test_prediction_history(prediction_context):
    """Перевіряє збереження кількох прогнозів."""

    user_id, task_id = prediction_context

    service = PredictionService()

    service.predict_task(user_id, task_id)
    service.predict_task(user_id, task_id)

    history = service.get_prediction_history(
        user_id,
        task_id
    )

    assert len(history) == 2


def test_latest_prediction(prediction_context):
    """Перевіряє отримання останнього результату."""

    user_id, task_id = prediction_context

    service = PredictionService()

    first = service.predict_task(
        user_id,
        task_id
    )

    second = service.predict_task(
        user_id,
        task_id
    )

    latest = service.get_latest_prediction(
        user_id,
        task_id
    )

    assert latest.id == second["prediction"].id

    assert latest.id != first["prediction"].id


def test_prediction_does_not_cross_users(prediction_context):
    """Перевіряє захист прогнозів від доступу іншого користувача."""

    _, task_id = prediction_context

    service = PredictionService()

    with pytest.raises(TaskNotFoundError):
        service.predict_task(
            user_id=9999,
            task_id=task_id
        )



def test_completed_task_cannot_be_predicted():
    """Перевіряє, що завершене завдання не прогнозується."""

    application = create_app(TestConfig)

    with application.app_context():
        db.create_all()

        try:
            user = User(
                username="completed_user",
                email="completed@example.com"
            )

            user.set_password("TestPassword123")

            db.session.add(user)
            db.session.flush()

            task = Task(
                user_id=user.id,
                title="Завершене завдання",
                priority="HIGH",
                status="NEW",
                deadline=(
                    datetime.now(timezone.utc).replace(tzinfo=None)
                    + timedelta(days=2)
                ),
                estimated_duration_minutes=60,
            )

            db.session.add(task)
            db.session.flush()

            task.update_status("COMPLETED")
            db.session.commit()

            service = PredictionService()

            with pytest.raises(ValueError):
                service.predict_task(user.id, task.id)

        finally:
            db.session.remove()

        try:
            db.drop_all()
        finally:
            db.engine.dispose()
