
from flask import Flask

from config import Config
from app.extensions import db, login_manager
from app.routes.prediction_routes import prediction_bp
from app.routes.ai_analytics_routes import ai_analytics_bp
from app.routes.page_routes import pages_bp
from app.routes.auth_routes import auth_bp
from app.routes.task_routes import task_bp
from app.routes.category_routes import category_bp


def create_app(config_class=Config):
    """Створює та налаштовує Flask-застосунок."""

    # Створення Flask-застосунку
    app = Flask(
        __name__,
        instance_relative_config=True
    )

    # Завантаження конфігурації
    app.config.from_object(config_class)

    # Ініціалізація розширень
    db.init_app(app)
    login_manager.init_app(app)

    # Реєстрація моделей
    from app import models  # noqa: F401

    # Реєстрація маршрутів
    # Реєстрація маршрутів
    app.register_blueprint(auth_bp)
    app.register_blueprint(task_bp)
    app.register_blueprint(ai_analytics_bp)
    app.register_blueprint(category_bp)
    app.register_blueprint(pages_bp)
    app.register_blueprint(prediction_bp)

    # Створення відсутніх таблиць
    with app.app_context():
        db.create_all()

    # Перевірка працездатності
    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "application": "SmartTask"
        }, 200

    return app
