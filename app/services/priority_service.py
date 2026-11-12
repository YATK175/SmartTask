
from abc import ABC, abstractmethod
from datetime import datetime, timezone


class PriorityStrategy(ABC):
    """Базовий інтерфейс стратегій оцінювання пріоритету."""

    @abstractmethod
    def calculate_priority(self, task, context=None) -> float:
        """Повертає оцінку пріоритетності від 0 до 100."""
        raise NotImplementedError


def _get_deadline(task):
    """Нормалізує дедлайн до UTC без часового поясу."""

    deadline = task.deadline

    if deadline.tzinfo is not None:
        return deadline.astimezone(timezone.utc).replace(tzinfo=None)

    return deadline


def _get_priority_base(task):
    """Перетворює ручний пріоритет на числову оцінку."""

    scores = {
        "LOW": 5,
        "MEDIUM": 15,
        "HIGH": 25,
        "CRITICAL": 35,
    }

    return scores.get(task.priority, 15)


class DeadlinePriorityStrategy(PriorityStrategy):
    """Стратегія оцінювання за близькістю дедлайну."""

    def calculate_priority(self, task, context=None) -> float:
        deadline = _get_deadline(task)
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        if deadline <= now:
            return 100.0

        hours_left = (deadline - now).total_seconds() / 3600
        duration_hours = task.estimated_duration_minutes / 60

        deadline_score = min(
            45,
            15 / max(hours_left / 24, 0.25)
        )

        duration_score = min(
            20,
            duration_hours / max(hours_left, 1) * 20
        )

        total = (
            _get_priority_base(task)
            + deadline_score
            + duration_score
        )

        return round(min(total, 100), 2)


class WorkloadPriorityStrategy(PriorityStrategy):
    """Стратегія оцінювання за поточним навантаженням."""

    def calculate_priority(self, task, context=None) -> float:
        context = context or {}

        active_tasks_count = context.get(
            "active_tasks_count",
            0
        )

        try:
            active_tasks_count = int(active_tasks_count)
        except (TypeError, ValueError):
            raise ValueError(
                "Кількість активних завдань повинна бути числом."
            )

        if active_tasks_count < 0:
            raise ValueError(
                "Кількість активних завдань не може бути від'ємною."
            )

        duration_hours = task.estimated_duration_minutes / 60

        workload_score = min(
            active_tasks_count * 8,
            40
        )

        duration_score = min(
            duration_hours * 3,
            25
        )

        total = (
            _get_priority_base(task)
            + workload_score
            + duration_score
        )

        return round(min(total, 100), 2)
