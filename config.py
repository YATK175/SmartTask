
import os
from pathlib import Path
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = False  # Лише для локального HTTP

# Коренева директорія проєкту
BASE_DIR = Path(__file__).resolve().parent

# Директорія постійного зберігання
INSTANCE_DIR = BASE_DIR / "instance"

# Шлях до SQLite
DATABASE_PATH = INSTANCE_DIR / "smarttask.db"


class Config:
    """Основна конфігурація SmartTask."""

    # Секретний ключ Flask
    SECRET_KEY = os.environ.get(
        "SECRET_KEY",
        "dev-secret-key-change-before-deployment"
    )

    # Підключення до SQLite
    SQLALCHEMY_DATABASE_URI = (
        f"sqlite:///{DATABASE_PATH.as_posix()}"
    )

    # Вимкнення зайвого відстеження змін
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Параметри SQLite
    SQLALCHEMY_ENGINE_OPTIONS = {
        "connect_args": {
            "check_same_thread": False,
            "timeout": 30
        }
    }

    # Режим розробки
    DEBUG = os.environ.get("FLASK_DEBUG", "1") == "1"
