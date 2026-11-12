
import sqlite3

from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.engine import Engine


db = SQLAlchemy()

login_manager = LoginManager()
login_manager.session_protection = "strong"


@login_manager.user_loader
def load_user(user_id):
    """Завантажує користувача з бази за ID."""

    from app.models import User

    try:
        return db.session.get(User, int(user_id))
    except (ValueError, TypeError):
        return None


@login_manager.unauthorized_handler
def unauthorized():
    """Повертає JSON замість HTML-перенаправлення."""

    from flask import jsonify

    return jsonify({
        "error": "Необхідна авторизація."
    }), 401


@event.listens_for(Engine, "connect")
def enable_sqlite_foreign_keys(
    dbapi_connection,
    connection_record
):
    """Активує перевірку зовнішніх ключів SQLite."""

    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()

        try:
            cursor.execute("PRAGMA foreign_keys = ON")
        finally:
            cursor.close()
