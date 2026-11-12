
from app.extensions import db
from app.models import User


class UserRepository:
    """Репозиторій для роботи з користувачами."""

    @staticmethod
    def get_by_id(user_id: int):
        """Пошук користувача за ID."""
        return db.session.get(User, user_id)

    @staticmethod
    def get_by_email(email: str):
        """Пошук користувача за email."""
        normalized_email = email.strip().lower()

        statement = db.select(User).where(
            User.email == normalized_email
        )

        return db.session.scalar(statement)

    @staticmethod
    def get_by_username(username: str):
        """Пошук користувача за ім'ям."""
        statement = db.select(User).where(
            User.username == username.strip()
        )

        return db.session.scalar(statement)

    @staticmethod
    def add(user: User):
        """Додавання нового користувача."""
        db.session.add(user)
        db.session.flush()

        return user
