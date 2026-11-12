
from app.extensions import db
from app.models import Category


class CategoryRepository:
    """Репозиторій для роботи з категоріями."""

    @staticmethod
    def get_by_id(category_id: int):
        """Отримання категорії за ID."""
        return db.session.get(Category, category_id)

    @staticmethod
    def get_by_id_for_user(category_id: int, user_id: int):
        """Отримання категорії конкретного користувача."""
        statement = db.select(Category).where(
            Category.id == category_id,
            Category.user_id == user_id
        )

        return db.session.scalar(statement)

    @staticmethod
    def get_by_user(user_id: int):
        """Отримання всіх категорій користувача."""
        statement = (
            db.select(Category)
            .where(Category.user_id == user_id)
            .order_by(Category.name.asc())
        )

        return db.session.scalars(statement).all()

    @staticmethod
    def add(category: Category):
        """Створення категорії."""
        db.session.add(category)
        db.session.flush()

        return category

    @staticmethod
    def delete(category: Category):
        """Видалення категорії."""
        db.session.delete(category)
        db.session.flush()
    @staticmethod
    def get_by_name_for_user(name: str, user_id: int):
        """Перевіряє наявність категорії з такою назвою."""

        statement = db.select(Category).where(
            Category.user_id == user_id,
            Category.name == name
        )

        return db.session.scalar(statement)

    @staticmethod
    def update(category: Category):
        """Оновлює категорію."""

        db.session.add(category)
        db.session.flush()

        return category