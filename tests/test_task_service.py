
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func

from app import create_app
from app.extensions import db
from app.models import User, Category, TaskHistory
from app.services import (
    TaskService,
    TaskNotFoundError,
    TaskValidationError,
    DeadlinePriorityStrategy,
    WorkloadPriorityStrategy,
)


class TestConfig:
    """Конфігурація ізольованої тестової бази."""

    TESTING = True
    SECRET_KEY = "test-secret-key"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "connect_args": {
            "check_same_thread": False
        }
    }


@pytest.fixture
def app():
    """Створює ізольований Flask-застосунок."""

    application = create_app(TestConfig)

    try:
        with application.app_context():
            db.drop_all()
            db.create_all()

            yield application

    finally:
        with application.app_context():
            db.session.remove()

            try:
                db.drop_all()
            finally:
                db.engine.dispose()


@pytest.fixture
def users(app):
    """Створює двох тестових користувачів."""

    with app.app_context():
        first = User(
            username="tester",
            email="tester@example.com"
        )
        first.set_password("TestPassword123")

        second = User(
            username="another",
            email="another@example.com"
        )
        second.set_password("TestPassword456")

        db.session.add_all([first, second])
        db.session.commit()

        return first.id, second.id


@pytest.fixture
def categories(app, users):
    """Створює категорії для обох користувачів."""

    first_user_id, second_user_id = users

    with app.app_context():
        first = Category(
            user_id=first_user_id,
            name="Навчання"
        )

        second = Category(
            user_id=second_user_id,
            name="Особисте"
        )

        db.session.add_all([first, second])
        db.session.commit()

        return first.id, second.id


def task_data(
    title="Тестове завдання",
    priority="HIGH",
    category_id=None
):
    """Формує тестові дані завдання."""

    deadline = (
        datetime.now(timezone.utc)
        + timedelta(days=2)
    )

    return {
        "title": title,
        "description": "Опис тестового завдання",
        "priority": priority,
        "category_id": category_id,
        "deadline": deadline.isoformat(),
        "estimated_duration_minutes": 120,
    }


def count_history(task_id):
    """Повертає кількість записів історії."""

    return db.session.scalar(
        db.select(func.count())
        .select_from(TaskHistory)
        .where(TaskHistory.task_id == task_id)
    )


def test_create_task_and_history(app, users, categories):
    """Перевіряє створення завдання та історії."""

    with app.app_context():
        service = TaskService()

        user_id, _ = users
        category_id, _ = categories

        task = service.create_task(
            user_id,
            task_data(category_id=category_id)
        )

        assert task.id is not None
        assert task.status == "NEW"
        assert task.title == "Тестове завдання"
        assert count_history(task.id) == 1


def test_task_access_is_user_specific(app, users):
    """Перевіряє ізоляцію завдань між користувачами."""

    with app.app_context():
        service = TaskService()

        user_id, another_user_id = users

        task = service.create_task(
            user_id,
            task_data()
        )

        with pytest.raises(TaskNotFoundError):
            service.get_task(another_user_id, task.id)


def test_update_task_records_history(app, users):
    """Перевіряє редагування та історію змін."""

    with app.app_context():
        service = TaskService()
        user_id, _ = users

        task = service.create_task(
            user_id,
            task_data()
        )

        service.update_task(
            user_id,
            task.id,
            {"title": "Оновлене завдання"}
        )

        updated = service.get_task(
            user_id,
            task.id
        )

        assert updated.title == "Оновлене завдання"
        assert count_history(task.id) == 2


def test_change_task_status(app, users):
    """Перевіряє зміну статусу та запис історії."""

    with app.app_context():
        service = TaskService()
        user_id, _ = users

        task = service.create_task(
            user_id,
            task_data()
        )

        service.change_status(
            user_id,
            task.id,
            "IN_PROGRESS"
        )

        updated = service.get_task(user_id, task.id)

        assert updated.status == "IN_PROGRESS"
        assert count_history(task.id) == 2


def test_complete_task(app, users):
    """Перевіряє завершення завдання."""

    with app.app_context():
        service = TaskService()
        user_id, _ = users

        task = service.create_task(
            user_id,
            task_data()
        )

        service.complete_task(
            user_id,
            task.id,
            actual_duration_minutes=100
        )

        completed = service.get_task(
            user_id,
            task.id
        )

        assert completed.status == "COMPLETED"
        assert completed.completed_at is not None
        assert completed.actual_duration_minutes == 100


def test_reject_empty_task_title(app, users):
    """Перевіряє негативний сценарій."""

    with app.app_context():
        service = TaskService()
        user_id, _ = users

        data = task_data(title="   ")

        with pytest.raises(TaskValidationError):
            service.create_task(user_id, data)


def test_reject_another_users_category(app, users, categories):
    """Перевіряє належність категорії користувачу."""

    with app.app_context():
        service = TaskService()

        user_id, _ = users
        _, another_category_id = categories

        data = task_data(
            category_id=another_category_id
        )

        with pytest.raises(TaskValidationError):
            service.create_task(user_id, data)


def test_task_search_and_filter(app, users):
    """Перевіряє пошук та фільтрацію."""

    with app.app_context():
        service = TaskService()
        user_id, _ = users

        task = service.create_task(
            user_id,
            task_data(
                title="Лабораторна робота",
                priority="HIGH"
            )
        )

        service.create_task(
            user_id,
            task_data(
                title="Вивчення англійської",
                priority="LOW"
            )
        )

        service.change_status(
            user_id,
            task.id,
            "IN_PROGRESS"
        )

        results = service.get_tasks(
            user_id,
            status="IN_PROGRESS",
            priority="HIGH",
            search="Лабораторна"
        )

        assert len(results) == 1
        assert results[0].id == task.id


def test_delete_task_and_history(app, users):
    """Перевіряє видалення завдання та його історії."""

    with app.app_context():
        service = TaskService()
        user_id, _ = users

        task = service.create_task(
            user_id,
            task_data()
        )

        task_id = task.id

        service.delete_task(user_id, task_id)

        assert service.task_repository.get_by_id(task_id) is None
        assert count_history(task_id) == 0


def test_priority_strategies(app, users):
    """Перевіряє алгоритми Strategy Pattern."""

    with app.app_context():
        service = TaskService()
        user_id, _ = users

        task = service.create_task(
            user_id,
            task_data()
        )

        deadline_strategy = DeadlinePriorityStrategy()
        workload_strategy = WorkloadPriorityStrategy()

        deadline_score = deadline_strategy.calculate_priority(task)

        workload_score = workload_strategy.calculate_priority(
            task,
            {"active_tasks_count": 5}
        )

        assert 0 <= deadline_score <= 100
        assert 0 <= workload_score <= 100

        service.set_priority_strategy(workload_strategy)

        assert service.priority_strategy is workload_strategy
