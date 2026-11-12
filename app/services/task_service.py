
from datetime import datetime, timezone

from app.extensions import db
from app.models import Task, TaskHistory
from app.repositories import (
    CategoryRepository,
    TaskRepository,
)
from app.services.priority_service import DeadlinePriorityStrategy


class TaskValidationError(ValueError):
    """Помилка перевірки даних завдання."""


class TaskNotFoundError(LookupError):
    """Завдання не знайдено або воно недоступне користувачу."""


class TaskService:
    """Бізнес-логіка управління завданнями."""

    ALLOWED_PRIORITIES = {
        "LOW",
        "MEDIUM",
        "HIGH",
        "CRITICAL",
    }

    ALLOWED_STATUSES = {
        "NEW",
        "IN_PROGRESS",
        "COMPLETED",
        "CANCELLED",
    }

    EDITABLE_FIELDS = {
        "title",
        "description",
        "priority",
        "category_id",
        "deadline",
        "estimated_duration_minutes",
    }

    def __init__(
        self,
        task_repository=None,
        category_repository=None,
        priority_strategy=None,
    ):
        self.task_repository = (
            task_repository or TaskRepository
        )

        self.category_repository = (
            category_repository or CategoryRepository
        )

        self.priority_strategy = (
            priority_strategy or DeadlinePriorityStrategy()
        )

    def set_priority_strategy(self, strategy):
        """Встановлює алгоритм оцінювання пріоритету."""

        if not hasattr(strategy, "calculate_priority"):
            raise TypeError(
                "Стратегія повинна мати метод calculate_priority."
            )

        self.priority_strategy = strategy

    @staticmethod
    def _parse_deadline(value):
        """Перевіряє та нормалізує дату дедлайну."""

        if isinstance(value, datetime):
            deadline = value

        elif isinstance(value, str):
            try:
                deadline = datetime.fromisoformat(
                    value.strip().replace("Z", "+00:00")
                )
            except ValueError as error:
                raise TaskValidationError(
                    "Некоректний формат дедлайну."
                ) from error

        else:
            raise TaskValidationError(
                "Дедлайн повинен бути датою або рядком ISO 8601."
            )

        if deadline.tzinfo is not None:
            deadline = deadline.astimezone(
                timezone.utc
            ).replace(tzinfo=None)

        return deadline

    def _get_task_for_user(self, task_id, user_id):
        """Отримує завдання з перевіркою власника."""

        task = self.task_repository.get_by_id_for_user(
            task_id,
            user_id
        )

        if task is None:
            raise TaskNotFoundError(
                "Завдання не знайдено."
            )

        return task

    def _validate_category(self, category_id, user_id):
        """Перевіряє належність категорії користувачу."""

        if category_id is None:
            return

        if isinstance(category_id, bool):
            raise TaskValidationError(
                "Некоректний ідентифікатор категорії."
            )

        if not isinstance(category_id, int) or category_id <= 0:
            raise TaskValidationError(
                "Ідентифікатор категорії повинен бути додатним числом."
            )

        category = self.category_repository.get_by_id_for_user(
            category_id,
            user_id
        )

        if category is None:
            raise TaskValidationError(
                "Категорію не знайдено або вона недоступна."
            )

    def _validate_task_data(self, data, user_id, partial=False):
        """Перевіряє дані створення або редагування."""

        if not isinstance(data, dict):
            raise TaskValidationError(
                "Дані завдання повинні бути словником."
            )

        unknown_fields = set(data) - self.EDITABLE_FIELDS

        if unknown_fields:
            raise TaskValidationError(
                f"Невідомі поля: {', '.join(sorted(unknown_fields))}"
            )

        if not partial and "title" not in data:
            raise TaskValidationError(
                "Назва завдання обов'язкова."
            )

        if "title" in data:
            title = data["title"]

            if not isinstance(title, str) or not title.strip():
                raise TaskValidationError(
                    "Назва завдання не може бути порожньою."
                )

            if len(title.strip()) > 200:
                raise TaskValidationError(
                    "Назва завдання не повинна перевищувати 200 символів."
                )

        if "description" in data:
            description = data["description"]

            if description is not None and not isinstance(
                description, str
            ):
                raise TaskValidationError(
                    "Опис повинен бути текстом."
                )

        if "priority" in data:
            priority = data["priority"]

            if priority not in self.ALLOWED_PRIORITIES:
                raise TaskValidationError(
                    "Недопустимий пріоритет завдання."
                )

        if "deadline" in data:
            data["deadline"] = self._parse_deadline(
                data["deadline"]
            )
        elif not partial:
            raise TaskValidationError(
                "Дедлайн завдання обов'язковий."
            )

        if "category_id" in data:
            self._validate_category(
                data["category_id"],
                user_id
            )

        if "estimated_duration_minutes" in data:
            duration = data["estimated_duration_minutes"]

            if (
                isinstance(duration, bool)
                or not isinstance(duration, int)
                or duration <= 0
            ):
                raise TaskValidationError(
                    "Тривалість повинна бути додатним цілим числом хвилин."
                )

        return data

    @staticmethod
    def _save_history(
        task,
        user_id,
        event_type,
        old_status=None,
        new_status=None,
        old_deadline=None,
        new_deadline=None,
    ):
        """Додає запис до історії завдання."""

        history = TaskHistory(
            task_id=task.id,
            changed_by_user_id=user_id,
            event_type=event_type,
            old_status=old_status,
            new_status=new_status,
            old_deadline=old_deadline,
            new_deadline=new_deadline,
        )

        db.session.add(history)

    def create_task(self, user_id: int, data: dict):
        """Створює нове завдання."""

        data = self._validate_task_data(
            data.copy(),
            user_id
        )

        try:
            task = Task(
                user_id=user_id,
                category_id=data.get("category_id"),
                title=data["title"].strip(),
                description=data.get("description"),
                priority=data.get("priority", "MEDIUM"),
                status="NEW",
                deadline=data["deadline"],
                estimated_duration_minutes=data.get(
                    "estimated_duration_minutes",
                    60
                ),
            )

            self.task_repository.add(task)

            self._save_history(
                task=task,
                user_id=user_id,
                event_type="CREATED",
                new_status="NEW",
                new_deadline=task.deadline,
            )

            db.session.commit()

            return task

        except Exception:
            db.session.rollback()
            raise

    def get_task(self, user_id: int, task_id: int):
        """Отримує завдання користувача."""

        return self._get_task_for_user(
            task_id,
            user_id
        )

    def get_tasks(self, user_id: int, **filters):
        """Отримує завдання з пошуком і фільтрацією."""

        allowed_filters = {
            "status",
            "priority",
            "category_id",
            "search",
            "sort_by",
            "descending",
        }

        unknown_filters = set(filters) - allowed_filters

        if unknown_filters:
            raise TaskValidationError(
                "Невідомі параметри фільтрації."
            )

        if (
            filters.get("status") is not None
            and filters["status"] not in self.ALLOWED_STATUSES
        ):
            raise TaskValidationError(
                "Недопустимий статус для фільтрації."
            )

        if (
            filters.get("priority") is not None
            and filters["priority"] not in self.ALLOWED_PRIORITIES
        ):
            raise TaskValidationError(
                "Недопустимий пріоритет для фільтрації."
            )

        return self.task_repository.get_by_user(
            user_id=user_id,
            **filters
        )

    def update_task(
        self,
        user_id: int,
        task_id: int,
        data: dict
    ):
        """Редагує завдання користувача."""

        data = self._validate_task_data(
            data.copy(),
            user_id,
            partial=True
        )

        try:
            task = self._get_task_for_user(
                task_id,
                user_id
            )

            old_deadline = task.deadline
            changed_fields = []

            for field, value in data.items():
                if field == "title":
                    value = value.strip()

                if getattr(task, field) != value:
                    setattr(task, field, value)
                    changed_fields.append(field)

            if not changed_fields:
                return task

            event_type = (
                "DEADLINE_CHANGED"
                if "deadline" in changed_fields
                else "UPDATED"
            )

            self._save_history(
                task=task,
                user_id=user_id,
                event_type=event_type,
                old_deadline=(
                    old_deadline
                    if "deadline" in changed_fields
                    else None
                ),
                new_deadline=(
                    task.deadline
                    if "deadline" in changed_fields
                    else None
                ),
            )

            self.task_repository.update(task)
            db.session.commit()

            return task

        except Exception:
            db.session.rollback()
            raise

    def change_status(
        self,
        user_id: int,
        task_id: int,
        new_status: str
    ):
        """Змінює статус і записує історію."""

        if new_status not in self.ALLOWED_STATUSES:
            raise TaskValidationError(
                "Недопустимий статус завдання."
            )

        try:
            task = self._get_task_for_user(
                task_id,
                user_id
            )

            old_status = task.status

            if old_status == new_status:
                return task

            task.update_status(new_status)

            self._save_history(
                task=task,
                user_id=user_id,
                event_type="STATUS_CHANGED",
                old_status=old_status,
                new_status=new_status,
            )

            self.task_repository.update(task)
            db.session.commit()

            return task

        except Exception:
            db.session.rollback()
            raise

    def complete_task(
        self,
        user_id: int,
        task_id: int,
        actual_duration_minutes=None
    ):
        """Завершує завдання та зберігає фактичну тривалість."""

        if actual_duration_minutes is not None:
            if (
                isinstance(actual_duration_minutes, bool)
                or not isinstance(actual_duration_minutes, int)
                or actual_duration_minutes < 0
            ):
                raise TaskValidationError(
                    "Фактична тривалість повинна бути невід'ємним числом."
                )

        try:
            task = self._get_task_for_user(
                task_id,
                user_id
            )

            old_status = task.status

            if old_status == "COMPLETED":
                raise TaskValidationError(
                    "Завдання вже завершене."
                )

            task.update_status("COMPLETED")

            if actual_duration_minutes is not None:
                task.actual_duration_minutes = (
                    actual_duration_minutes
                )

            self._save_history(
                task=task,
                user_id=user_id,
                event_type="STATUS_CHANGED",
                old_status=old_status,
                new_status="COMPLETED",
            )

            self.task_repository.update(task)
            db.session.commit()

            return task

        except Exception:
            db.session.rollback()
            raise

    def delete_task(self, user_id: int, task_id: int):
        """Видаляє завдання користувача."""

        try:
            task = self._get_task_for_user(
                task_id,
                user_id
            )

            self.task_repository.delete(task)
            db.session.commit()

            return True

        except Exception:
            db.session.rollback()
            raise

    def calculate_priority_score(
        self,
        task: Task,
        context=None
    ) -> float:
        """Обчислює рейтинг пріоритетності завдання."""

        return self.priority_strategy.calculate_priority(
            task,
            context
        )

    def rank_tasks(self, tasks, context=None):
        """Сортує завдання за алгоритмічною оцінкою пріоритету."""

        return sorted(
            tasks,
            key=lambda task: self.calculate_priority_score(
                task,
                context
            ),
            reverse=True
        )
