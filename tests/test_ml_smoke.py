
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app import create_app
from app.extensions import db
from app.models import User, Task

from app.intelligence.feature_engineering import (
    build_task_features,
)
from app.intelligence.risk_predictor import RiskPredictor
from app.intelligence.recommendation_service import (
    RecommendationService,
)


class TestConfig:
    TESTING = True
    SECRET_KEY = "ml-test-secret"

    SQLALCHEMY_DATABASE_URI = "sqlite://"

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SQLALCHEMY_ENGINE_OPTIONS = {
        "connect_args": {
            "check_same_thread": False
        }
    }


@pytest.fixture
def task_context():
    """Створює тестове завдання в тимчасовій БД."""

    app = create_app(TestConfig)

    with app.app_context():
        db.create_all()

        user = User(
            username="ml_tester",
            email="ml@example.com"
        )

        user.set_password("TestPassword123")

        db.session.add(user)
        db.session.flush()

        task = Task(
            user_id=user.id,
            title="Тестування ML-прогнозу",
            description="Тестове завдання",
            priority="HIGH",
            status="NEW",
            deadline=(
                datetime.now(timezone.utc).replace(tzinfo=None)
                + timedelta(days=2)
            ),
            estimated_duration_minutes=240,
        )

        db.session.add(task)
        db.session.commit()

        yield task

        # Close the current SQLAlchemy session.
        db.session.remove()

        # Drop all tables and dispose the SQLite connection pool.
        try:
            db.drop_all()
        finally:
            db.engine.dispose()


def test_feature_engineering(task_context):
    """Перевіряє формування шести ознак."""

    features = build_task_features(task_context)

    assert len(features) == 6

    assert features["priority_level"] == 3

    assert 0.25 <= features["days_until_deadline"] <= 21

    assert 0.25 <= features["estimated_duration_hours"] <= 24

    assert 0 <= features["active_tasks_count"] <= 18

    assert 0 <= features["on_time_completion_rate"] <= 1

    assert 0 <= features["task_age_days"] <= 14


def test_random_forest_prediction(task_context):
    """Перевіряє прогнозування Random Forest."""

    predictor = RiskPredictor()

    result = predictor.predict(task_context)

    assert result["source"] == "ML"

    assert result["model_version"] == "rf-synthetic-v2"

    assert 0 <= result["risk_score"] <= 1

    assert result["risk_level"] in {
        "LOW",
        "MEDIUM",
        "HIGH"
    }

    assert isinstance(result["is_at_risk"], bool)


def test_fallback_prediction(task_context):
    """Перевіряє резервний алгоритм."""

    predictor = RiskPredictor(
        model_path=Path("missing_model.joblib")
    )

    result = predictor.predict(task_context)

    assert result["source"] == "FALLBACK"

    assert 0 <= result["risk_score"] <= 1

    assert result["model_version"] is None


def test_recommendations(task_context):
    """Перевіряє генерацію рекомендацій."""

    predictor = RiskPredictor()
    prediction = predictor.predict(task_context)

    service = RecommendationService()

    result = service.generate(
        task_context,
        prediction
    )

    assert result["risk_level"] in {
        "LOW",
        "MEDIUM",
        "HIGH"
    }

    assert isinstance(
        result["recommendations"],
        list
    )

    assert len(result["recommendations"]) > 0

def test_recommendation_explanations(task_context):
    """Перевіряє формування контекстних пояснень."""

    predictor = RiskPredictor()

    prediction = predictor.predict(task_context)

    service = RecommendationService()

    result = service.generate(
        task_context,
        prediction
    )

    assert "contextual_factors" in result

    factors = result["contextual_factors"]

    assert len(factors) == 5

    for factor in factors:
        assert "name" in factor
        assert "value" in factor
        assert "level" in factor
        assert "explanation" in factor

        assert factor["level"] in {
            "LOW",
            "MEDIUM",
            "HIGH"
        }

    factor_names = {
        factor["name"]
        for factor in factors
    }

    assert "Дедлайн" in factor_names
    assert "Тривалість роботи" in factor_names
    assert "Активні завдання" in factor_names
    assert "Своєчасне виконання" in factor_names
    assert "Вік завдання" in factor_names
