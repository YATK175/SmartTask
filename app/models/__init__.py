from app.models.user import User
from app.models.category import Category
from app.models.task import Task
from app.models.task_history import TaskHistory
from app.models.prediction import Prediction

__all__ = [
    "User",
    "Category",
    "Task",
    "TaskHistory",
    "Prediction",
]

from flask import Flask
from config import Config
from app.extensions import db


def create_app(config_class=Config):
    """Створює та налаштовує Flask-застосунок."""

    app = Flask(
        __name__,
        instance_relative_config=True
    )

    app.config.from_object(config_class)

    db.init_app(app)

    # Реєстрація моделей у metadata SQLAlchemy
    from app import models  # noqa: F401

    # Створення відсутніх таблиць
    with app.app_context():
        db.create_all()

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "application": "SmartTask"
        }, 200

    return app