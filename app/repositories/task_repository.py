
from sqlalchemy import or_

from app.extensions import db
from app.models import Task


class TaskRepository:
    """Репозиторій для роботи із завданнями."""

    @staticmethod
    def get_by_id(task_id: int):
        """Отримання завдання за ID."""
        return db.session.get(Task, task_id)

    @staticmethod
    def get_by_id_for_user(task_id: int, user_id: int):
        """Отримання завдання конкретного користувача."""
        statement = db.select(Task).where(
            Task.id == task_id,
            Task.user_id == user_id
        )

        return db.session.scalar(statement)

    @staticmethod
    def get_by_user(
        user_id: int,
        status: str = None,
        priority: str = None,
        category_id: int = None,
        search: str = None,
        sort_by: str = "deadline",
        descending: bool = False
    ):
        """Отримання завдань з пошуком, фільтрацією та сортуванням."""

        statement = db.select(Task).where(
            Task.user_id == user_id
        )

        # Фільтрація за статусом
        if status:
            statement = statement.where(
                Task.status == status
            )

        # Фільтрація за пріоритетом
        if priority:
            statement = statement.where(
                Task.priority == priority
            )

        # Фільтрація за категорією
        if category_id is not None:
            statement = statement.where(
                Task.category_id == category_id
            )

        # Пошук за назвою або описом
        if search and search.strip():
            search_pattern = f"%{search.strip()}%"

            statement = statement.where(
                or_(
                    Task.title.ilike(search_pattern),
                    Task.description.ilike(search_pattern)
                )
            )

        # Дозволені поля сортування
        sort_columns = {
            "deadline": Task.deadline,
            "priority": Task.priority,
            "created_at": Task.created_at,
            "title": Task.title
        }

        # Захист від довільної назви поля
        sort_column = sort_columns.get(
            sort_by,
            Task.deadline
        )

        if descending:
            statement = statement.order_by(
                sort_column.desc()
            )
        else:
            statement = statement.order_by(
                sort_column.asc()
            )

        return db.session.scalars(statement).all()

    @staticmethod
    def add(task: Task):
        """Створення завдання."""
        db.session.add(task)
        db.session.flush()

        return task

    @staticmethod
    def update(task: Task):
        """Оновлення завдання."""
        db.session.add(task)
        db.session.flush()

        return task

    @staticmethod
    def delete(task: Task):
        """Видалення завдання."""
        db.session.delete(task)
        db.session.flush()
