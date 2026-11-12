
from datetime import datetime, timezone

from sqlalchemy import func

from app.extensions import db
from app.models import Task


PRIORITY_MAPPING = {
    "LOW": 1,
    "MEDIUM": 2,
    "HIGH": 3,
    "CRITICAL": 4,
}

# Середнє значення Beta(5, 3), яку використовували
# під час генерації синтетичного навчального набору.
COLD_START_RATE = 0.625

# Кількість умовних попередніх спостережень для згладжування.
PRIOR_RATE_WEIGHT = 5


def normalize_datetime(value):
    """Перетворює дату на UTC datetime без timezone."""

    if value is None:
        return None

    if value.tzinfo is not None:
        return value.astimezone(
            timezone.utc
        ).replace(tzinfo=None)

    return value


def calculate_on_time_rate(user_id: int) -> float:
    """
    Обчислює частку завдань, виконаних вчасно.

    Для користувачів без історії використовуємо
    нейтральне початкове значення.
    """

    completed_tasks = db.session.scalars(
        db.select(Task).where(
            Task.user_id == user_id,
            Task.status == "COMPLETED",
            Task.completed_at.is_not(None),
        )
    ).all()

    completed_count = 0
    on_time_count = 0

    for task in completed_tasks:
        completed_at = normalize_datetime(task.completed_at)
        deadline = normalize_datetime(task.deadline)

        if completed_at is None or deadline is None:
            continue

        completed_count += 1

        if completed_at <= deadline:
            on_time_count += 1

    rate = (
        on_time_count
        + PRIOR_RATE_WEIGHT * COLD_START_RATE
    ) / (
        completed_count + PRIOR_RATE_WEIGHT
    )

    return round(
        min(max(rate, 0.0), 1.0),
        4
    )


def count_active_tasks(user_id: int, exclude_task_id: int) -> int:
    """Рахує інші активні завдання користувача."""

    count = db.session.scalar(
        db.select(func.count(Task.id)).where(
            Task.user_id == user_id,
            Task.status.in_(["NEW", "IN_PROGRESS"]),
            Task.id != exclude_task_id,
        )
    )

    return min(max(int(count or 0), 0), 18)


def build_task_features(task: Task) -> dict:
    """
    Формує ознаки для Random Forest.

    Повертає рівно шість характеристик,
    які відповідають FEATURE_COLUMNS.
    """

    if task.deadline is None:
        raise ValueError(
            "Для прогнозування завдання повинен мати дедлайн."
        )

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    deadline = normalize_datetime(task.deadline)
    created_at = normalize_datetime(task.created_at)

    if created_at is None:
        created_at = now

    seconds_left = (
        deadline - now
    ).total_seconds()

    # Значення обмежуються діапазонами
    # синтетичного навчального набору.
    days_until_deadline = max(
        0.25,
        min(seconds_left / 86400, 21.0)
    )

    estimated_duration_hours = max(
        0.25,
        min(
            task.estimated_duration_minutes / 60,
            24.0
        )
    )

    task_age_days = max(
        0.0,
        min(
            (now - created_at).total_seconds() / 86400,
            14.0
        )
    )

    return {
        "priority_level": PRIORITY_MAPPING.get(
            task.priority,
            2
        ),
        "days_until_deadline": round(
            days_until_deadline,
            4
        ),
        "estimated_duration_hours": round(
            estimated_duration_hours,
            4
        ),
        "active_tasks_count": count_active_tasks(
            task.user_id,
            task.id
        ),
        "on_time_completion_rate": calculate_on_time_rate(
            task.user_id
        ),
        "task_age_days": round(
            task_age_days,
            4
        ),
    }
