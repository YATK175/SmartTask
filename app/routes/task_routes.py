
from flask import Blueprint, jsonify, request, current_app
from flask_login import current_user, login_required

from app.services import (
    TaskService,
    TaskValidationError,
    TaskNotFoundError,
    PredictionService,
)


task_bp = Blueprint(
    "tasks",
    __name__,
    url_prefix="/api/tasks"
)


# Ініціалізація сервісів
task_service = TaskService()
prediction_service = PredictionService()

# Поля, зміна яких вимагає повторного ML-прогнозування
PREDICTION_INPUT_FIELDS = {
    "priority",
    "deadline",
    "estimated_duration_minutes",
}



def serialize_task(task):
    """Перетворює модель Task на JSON-сумісний словник."""

    return {
        "id": task.id,
        "user_id": task.user_id,
        "category_id": task.category_id,
        "title": task.title,
        "description": task.description,
        "priority": task.priority,
        "status": task.status,
        "deadline": task.deadline.isoformat(),
        "estimated_duration_minutes": (
            task.estimated_duration_minutes
        ),
        "actual_duration_minutes": (
            task.actual_duration_minutes
        ),
        "is_overdue": task.is_overdue(),
        "created_at": (
            task.created_at.isoformat()
            if task.created_at else None
        ),
        "updated_at": (
            task.updated_at.isoformat()
            if task.updated_at else None
        ),
        "completed_at": (
            task.completed_at.isoformat()
            if task.completed_at else None
        ),
    }


def get_json_data():
    """Перевіряє, що запит містить JSON-об'єкт."""

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return None

    return data


def parse_bool(value, default=False):
    """Перетворює рядок запиту на boolean."""

    if value is None:
        return default

    normalized = value.strip().lower()

    if normalized in {"true", "1", "yes"}:
        return True

    if normalized in {"false", "0", "no"}:
        return False

    raise TaskValidationError(
        "Параметр descending повинен бути true або false."
    )


def parse_optional_int(value, field_name):
    """Перевіряє необов'язковий числовий параметр."""

    if value is None:
        return None

    try:
        result = int(value)
    except (ValueError, TypeError):
        raise TaskValidationError(
            f"Параметр {field_name} повинен бути цілим числом."
        )

    if result <= 0:
        raise TaskValidationError(
            f"Параметр {field_name} повинен бути додатним."
        )

    return result


@task_bp.get("")
@login_required
def get_tasks():
    """Отримує список завдань поточного користувача."""

    try:
        filters = {
            "status": request.args.get("status"),
            "priority": request.args.get("priority"),
            "category_id": parse_optional_int(
                request.args.get("category_id"),
                "category_id"
            ),
            "search": request.args.get("search"),
            "sort_by": request.args.get(
                "sort_by",
                "deadline"
            ),
            "descending": parse_bool(
                request.args.get("descending")
            ),
        }

        allowed_sort_fields = {
            "deadline",
            "priority",
            "created_at",
            "title",
        }

        if filters["sort_by"] not in allowed_sort_fields:
            raise TaskValidationError(
                "Недопустиме поле сортування."
            )

        tasks = task_service.get_tasks(
            current_user.id,
            **filters
        )

        return jsonify({
            "count": len(tasks),
            "tasks": [
                serialize_task(task)
                for task in tasks
            ]
        }), 200

    except TaskValidationError as error:
        return jsonify({"error": str(error)}), 400


@task_bp.post("")
@login_required
def create_task():
    """Створює нове завдання."""

    data = get_json_data()

    if data is None:
        return jsonify({
            "error": "Очікується JSON-об'єкт."
        }), 400

    try:
        task = task_service.create_task(
            current_user.id,
            data
        )

        return jsonify({
            "message": "Завдання успішно створено.",
            "task": serialize_task(task)
        }), 201

    except TaskValidationError as error:
        return jsonify({"error": str(error)}), 400


@task_bp.get("/<int:task_id>")
@login_required
def get_task(task_id):
    """Отримує конкретне завдання."""

    try:
        task = task_service.get_task(
            current_user.id,
            task_id
        )

        return jsonify({
            "task": serialize_task(task)
        }), 200

    except TaskNotFoundError as error:
        return jsonify({"error": str(error)}), 404





@task_bp.delete("/<int:task_id>")
@login_required
def delete_task(task_id):
    """Видаляє завдання."""

    try:
        task_service.delete_task(
            current_user.id,
            task_id
        )

        return jsonify({
            "message": "Завдання успішно видалено."
        }), 200

    except TaskNotFoundError as error:
        return jsonify({"error": str(error)}), 404



@task_bp.patch("/<int:task_id>")
@login_required
def update_task(task_id):
    """Оновлює завдання та за потреби повторює ML-прогноз."""

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "error": "Очікується JSON-об'єкт."
        }), 400

    # Перевіряємо, чи змінюються параметри прогнозування.
    should_refresh_prediction = bool(
        set(data.keys()) & PREDICTION_INPUT_FIELDS
    )

    try:
        # Перевіряємо наявність попереднього прогнозу.
        previous_prediction = None

        if should_refresh_prediction:
            previous_prediction = (
                prediction_service.get_latest_prediction(
                    current_user.id,
                    task_id
                )
            )

        # Оновлюємо завдання.
        task = task_service.update_task(
            current_user.id,
            task_id,
            data
        )

        prediction_refresh = None

        # Повторний аналіз тільки якщо:
        # 1. Змінено параметр прогнозування.
        # 2. Раніше вже існував прогноз.
        # 3. Завдання залишається активним.
        if (
            should_refresh_prediction
            and previous_prediction is not None
            and task.status in {"NEW", "IN_PROGRESS"}
        ):
            try:
                result = prediction_service.predict_task(
                    current_user.id,
                    task_id
                )

                prediction = result["prediction"]

                prediction_refresh = {
                    "status": "updated",
                    "risk_score": prediction.risk_score,
                    "risk_level": prediction.risk_level,
                    "source": prediction.source,
                    "model_version": prediction.model_version,
                }

            except Exception:
                current_app.logger.exception(
                    "Automatic prediction refresh failed "
                    "for task %s",
                    task_id
                )

                prediction_refresh = {
                    "status": "failed",
                    "message": (
                        "Завдання оновлено, але прогноз "
                        "не вдалося перерахувати."
                    )
                }

        return jsonify({
            "message": "Завдання оновлено.",
            "task": serialize_task(task),
            "prediction_refresh": prediction_refresh,
        }), 200

    except TaskValidationError as error:
        return jsonify({
            "error": str(error)
        }), 400

    except TaskNotFoundError as error:
        return jsonify({
            "error": str(error)
        }), 404



@task_bp.post("/<int:task_id>/complete")
@login_required
def complete_task(task_id):
    """Завершує завдання."""

    data = get_json_data()

    if data is None:
        return jsonify({
            "error": "Очікується JSON-об'єкт."
        }), 400

    try:
        task = task_service.complete_task(
            current_user.id,
            task_id,
            data.get("actual_duration_minutes")
        )

        return jsonify({
            "message": "Завдання завершено.",
            "task": serialize_task(task)
        }), 200

    except TaskValidationError as error:
        return jsonify({"error": str(error)}), 400

    except TaskNotFoundError as error:
        return jsonify({"error": str(error)}), 404
