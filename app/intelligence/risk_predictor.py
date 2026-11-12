
import logging

from pathlib import Path

import joblib
import pandas as pd

from app.intelligence.feature_engineering import (
    build_task_features,
)


logger = logging.getLogger(__name__)

MODEL_PATH = (
    Path(__file__).resolve().parent
    / "artifacts"
    / "task_risk_model.joblib"
)

# Порогові значення рівнів ризику.
LOW_RISK_LIMIT = 0.30
HIGH_RISK_LIMIT = 0.65

FALLBACK_ALERT_THRESHOLD = 0.30


class RiskPredictor:
    """Прогнозує ризик прострочення завдань."""

    def __init__(self, model_path=None):
        self.model_path = Path(
            model_path or MODEL_PATH
        )

        self._bundle = None

    def _load_model(self):
        """Завантажує навчений Random Forest."""

        if self._bundle is not None:
            return self._bundle

        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Модель не знайдена: {self.model_path}"
            )

        bundle = joblib.load(self.model_path)

        required_keys = {
            "model",
            "feature_columns",
            "threshold",
            "model_version",
        }

        if not isinstance(bundle, dict):
            raise ValueError(
                "Некоректний формат файлу моделі."
            )

        if not required_keys.issubset(bundle):
            raise ValueError(
                "Файл моделі не містить необхідних параметрів."
            )

        if not callable(
            getattr(bundle["model"], "predict_proba", None)
        ):
            raise ValueError(
                "Модель не підтримує predict_proba."
            )

        self._bundle = bundle

        return self._bundle

    @staticmethod
    def _get_risk_level(risk_score: float) -> str:
        """Перетворює оцінку ризику на категорію."""

        if risk_score < LOW_RISK_LIMIT:
            return "LOW"

        if risk_score < HIGH_RISK_LIMIT:
            return "MEDIUM"

        return "HIGH"

    @staticmethod
    def _fallback_score(features: dict) -> float:
        """
        Резервний алгоритм оцінювання.

        Це детермінована евристика, а не машинне навчання.
        """

        score = 0.10

        days_left = features["days_until_deadline"]
        duration = features["estimated_duration_hours"]
        active_tasks = features["active_tasks_count"]
        completion_rate = features["on_time_completion_rate"]
        task_age = features["task_age_days"]
        priority = features["priority_level"]

        # Близькість дедлайну.
        if days_left <= 1:
            score += 0.35
        elif days_left <= 3:
            score += 0.25
        elif days_left <= 7:
            score += 0.12

        # Співвідношення тривалості та доступного часу.
        available_hours = max(days_left * 6, 1)

        workload_ratio = duration / available_hours

        if workload_ratio >= 1:
            score += 0.25
        elif workload_ratio >= 0.5:
            score += 0.12

        # Кількість активних завдань.
        if active_tasks >= 8:
            score += 0.15
        elif active_tasks >= 5:
            score += 0.08

        # Історія виконання.
        if completion_rate < 0.45:
            score += 0.15
        elif completion_rate < 0.60:
            score += 0.08

        # Вік завдання.
        if task_age >= 7:
            score += 0.05

        # Менший пріоритет за умовами нашої
        # симуляційної моделі трохи підвищує ризик.
        if priority == 1:
            score += 0.04
        elif priority == 2:
            score += 0.02

        return round(
            min(max(score, 0.0), 1.0),
            4
        )

    @staticmethod
    def _build_result(
        risk_score,
        features,
        source,
        model_version=None,
        is_at_risk=None,
        reason=None,
        threshold=None
    ):
        """Створює стандартизований результат прогнозу."""

        score = float(
            min(max(risk_score, 0.0), 1.0)
        )

        if is_at_risk is None:
            is_at_risk = score >= FALLBACK_ALERT_THRESHOLD

        return {
            "risk_score": round(score, 4),
            "risk_level": RiskPredictor._get_risk_level(score),
            "source": source,
            "model_version": model_version,
            "features_snapshot": features,
            "is_at_risk": bool(is_at_risk),
            "classification_threshold": threshold,
            "reason": reason,
        }

    def _fallback_prediction(self, features, reason):
        """Формує прогноз резервним алгоритмом."""

        score = self._fallback_score(features)

        return self._build_result(
            risk_score=score,
            features=features,
            source="FALLBACK",
            reason=reason,
            threshold=FALLBACK_ALERT_THRESHOLD,
        )

    def predict(self, task):
        """Обчислює ризик прострочення завдання."""

        if task is None:
            raise ValueError(
                "Не передано завдання для прогнозування."
            )

        if task.status in {"COMPLETED", "CANCELLED"}:
            raise ValueError(
                "Не можна прогнозувати завершене або скасоване завдання."
            )

        features = build_task_features(task)

        # Якщо дедлайн уже минув, це відомий факт,
        # а не прогноз майбутньої події.
        if task.is_overdue():
            return self._build_result(
                risk_score=1.0,
                features=features,
                source="FALLBACK",
                is_at_risk=True,
                reason="Дедлайн завдання вже минув.",
                threshold=FALLBACK_ALERT_THRESHOLD,
            )

        try:
            bundle = self._load_model()

            model = bundle["model"]
            feature_columns = bundle["feature_columns"]
            threshold = float(bundle["threshold"])

            if not 0 <= threshold <= 1:
                raise ValueError(
                    "Некоректний поріг класифікації."
                )

            input_data = pd.DataFrame(
                [[features[column] for column in feature_columns]],
                columns=feature_columns
            )

            overdue_index = list(model.classes_).index(1)

            probability = float(
                model.predict_proba(input_data)[
                    0,
                    overdue_index
                ]
            )

            return self._build_result(
                risk_score=probability,
                features=features,
                source="ML",
                model_version=bundle["model_version"],
                is_at_risk=probability >= threshold,
                reason=None,
                threshold=threshold,
            )

        except Exception as error:
            logger.exception(
                "ML prediction failed. Using fallback."
            )

            return self._fallback_prediction(
                features,
                reason=f"ML недоступний: {type(error).__name__}"
            )
