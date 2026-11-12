
from flask import Blueprint, jsonify
from flask_login import current_user, login_required

from app.services import (
    PredictionService,
    TaskNotFoundError,
)


prediction_bp = Blueprint(
    "predictions",
    __name__,
    url_prefix="/api/predictions"
)

prediction_service = PredictionService()


def serialize_prediction(prediction):
    """Перетворює результат прогнозування на JSON."""

    return {
        "id": prediction.id,
        "task_id": prediction.task_id,
        "risk_score": prediction.risk_score,
        "risk_percentage": round(prediction.risk_score * 100, 2),
        "risk_level": prediction.risk_level,
        "source": prediction.source,
        "model_version": prediction.model_version,
        "features_snapshot": prediction.get_features(),
        "created_at": (
            prediction.created_at.isoformat()
            if prediction.created_at else None
        ),
    }


@prediction_bp.post("/tasks/<int:task_id>")
@login_required
def predict_task(task_id):
    """Запускає прогнозування ризику завдання."""

    try:
        result = prediction_service.predict_task(
            current_user.id,
            task_id
        )

        prediction = result["prediction"]
        analysis = result["analysis"]

        return jsonify({
            "message": "Аналіз завдання завершено.",
            "prediction": serialize_prediction(prediction),
            "analysis": analysis,
            "notice": (
                "Експериментальна модель навчена на синтетичних "
                "даних. Результат не є підтвердженою ймовірністю "
                "прострочення для реального користувача."
                if prediction.source == "ML"
                else
                "Використано резервний алгоритм оцінювання."
            )
        }), 201

    except TaskNotFoundError as error:
        return jsonify({
            "error": str(error)
        }), 404

    except ValueError as error:
        return jsonify({
            "error": str(error)
        }), 400


@prediction_bp.get("/tasks/<int:task_id>")
@login_required
def get_prediction_history(task_id):
    """Отримує історію прогнозів завдання."""

    try:
        predictions = (
            prediction_service.get_prediction_history(
                current_user.id,
                task_id
            )
        )

        return jsonify({
            "task_id": task_id,
            "count": len(predictions),
            "predictions": [
                serialize_prediction(item)
                for item in predictions
            ]
        }), 200

    except TaskNotFoundError as error:
        return jsonify({
            "error": str(error)
        }), 404


@prediction_bp.get("/tasks/<int:task_id>/latest")
@login_required
def get_latest_prediction(task_id):
    """Отримує останній прогноз завдання."""

    try:
        prediction = (
            prediction_service.get_latest_prediction(
                current_user.id,
                task_id
            )
        )

        if prediction is None:
            return jsonify({
                "error": "Для цього завдання ще немає прогнозів."
            }), 404

        return jsonify({
            "prediction": serialize_prediction(prediction)
        }), 200

    except TaskNotFoundError as error:
        return jsonify({
            "error": str(error)
        }), 404
