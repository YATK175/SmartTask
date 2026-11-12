
import json

from pathlib import Path

from flask import Blueprint, jsonify
from flask_login import current_user, login_required

from app.services import PredictionService


ai_analytics_bp = Blueprint(
    "ai_analytics",
    __name__,
    url_prefix="/api/ai-analytics"
)

prediction_service = PredictionService()

METRICS_PATH = (
    Path(__file__).resolve().parents[1]
    / "intelligence"
    / "artifacts"
    / "metrics.json"
)


@ai_analytics_bp.get("/summary")
@login_required
def get_ai_summary():
    """Повертає статистику прогнозів користувача."""

    result = prediction_service.get_user_analytics(
        current_user.id
    )

    return jsonify(result), 200


@ai_analytics_bp.get("/model-metrics")
@login_required
def get_model_metrics():
    """Повертає метрики останнього навчання Random Forest."""

    if not METRICS_PATH.exists():
        return jsonify({
            "error": "Метрики моделі ще не створені."
        }), 404

    try:
        with open(
            METRICS_PATH,
            "r",
            encoding="utf-8"
        ) as file:
            metrics = json.load(file)

        return jsonify(metrics), 200

    except (OSError, json.JSONDecodeError):
        return jsonify({
            "error": "Не вдалося прочитати метрики моделі."
        }), 500
