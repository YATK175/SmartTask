
from app.extensions import db
from app.models import Prediction
from app.repositories import (
    TaskRepository,
    PredictionRepository,
)
from app.intelligence.risk_predictor import RiskPredictor
from app.intelligence.recommendation_service import (
    RecommendationService,
)
from app.services.task_service import TaskNotFoundError


class PredictionService:
    """Координує прогнозування та збереження результатів."""

    def __init__(
        self,
        task_repository=None,
        prediction_repository=None,
        predictor=None,
        recommendation_service=None,
    ):
        self.task_repository = (
            task_repository or TaskRepository
        )

        self.prediction_repository = (
            prediction_repository or PredictionRepository
        )

        self.predictor = predictor or RiskPredictor()

        self.recommendation_service = (
            recommendation_service or RecommendationService()
        )

    def predict_task(self, user_id: int, task_id: int):
        """Виконує прогноз і зберігає результат у БД."""

        task = self.task_repository.get_by_id_for_user(
            task_id,
            user_id
        )

        if task is None:
            raise TaskNotFoundError(
                "Завдання не знайдено."
            )

        try:
            # Крок 1. Отримання прогнозу.
            prediction_result = self.predictor.predict(task)

            # Крок 2. Генерація рекомендацій.
            analysis = self.recommendation_service.generate(
                task,
                prediction_result
            )

            # Крок 3. Формування знімка ознак та параметрів рішення.
            snapshot = {
                "features": prediction_result["features_snapshot"],
                "classification_threshold": (
                    prediction_result["classification_threshold"]
                ),
                "is_at_risk": prediction_result["is_at_risk"],
                "reason": prediction_result.get("reason"),
                "dataset_type": (
                    "synthetic"
                    if prediction_result["source"] == "ML"
                    else "rule_based"
                ),
            }

            # Крок 4. Створення запису Prediction.
            prediction = Prediction(
                task_id=task.id,
                risk_score=prediction_result["risk_score"],
                risk_level=prediction_result["risk_level"],
                source=prediction_result["source"],
                model_version=prediction_result["model_version"],
            )

            prediction.set_features(snapshot)

            # Крок 5. Збереження в межах однієї транзакції.
            self.prediction_repository.add(prediction)

            db.session.commit()

            return {
                "prediction": prediction,
                "analysis": analysis,
            }

        except Exception:
            db.session.rollback()
            raise

    def get_prediction_history(
        self,
        user_id: int,
        task_id: int
    ):
        """Повертає історію прогнозів завдання."""

        task = self.task_repository.get_by_id_for_user(
            task_id,
            user_id
        )

        if task is None:
            raise TaskNotFoundError(
                "Завдання не знайдено."
            )

        return self.prediction_repository.get_by_task_for_user(
            task_id,
            user_id
        )

    def get_latest_prediction(
        self,
        user_id: int,
        task_id: int
    ):
        """Повертає останній прогноз."""

        task = self.task_repository.get_by_id_for_user(
            task_id,
            user_id
        )

        if task is None:
            raise TaskNotFoundError(
                "Завдання не знайдено."
            )

        return self.prediction_repository.get_latest_for_task(
            task_id,
            user_id
        )

    def get_user_analytics(self, user_id: int):
        """
        Формує аналітику ризиків за останніми прогнозами
        кожного завдання користувача.
        """

        tasks = self.task_repository.get_by_user(user_id)

        predictions = (
            self.prediction_repository.get_all_for_user(user_id)
        )

        # Залишаємо тільки найновіший прогноз кожного завдання.
        latest_by_task = {}

        for prediction in predictions:
            latest_by_task.setdefault(
                prediction.task_id,
                prediction
            )

        summary = {
            "total_tasks": len(tasks),
            "analyzed_tasks": 0,
            "unanalyzed_tasks": 0,
            "low_risk": 0,
            "medium_risk": 0,
            "high_risk": 0,
            "overdue_tasks": 0,
        }

        result_tasks = []

        for task in tasks:
            latest = latest_by_task.get(task.id)

            if task.is_overdue():
                summary["overdue_tasks"] += 1

            prediction_data = None

            if latest is not None:
                summary["analyzed_tasks"] += 1

                level = latest.risk_level.lower()

                if level == "low":
                    summary["low_risk"] += 1
                elif level == "medium":
                    summary["medium_risk"] += 1
                elif level == "high":
                    summary["high_risk"] += 1

                snapshot = latest.get_features() or {}

                prediction_data = {
                    "id": latest.id,
                    "risk_score": latest.risk_score,
                    "risk_percentage": round(
                        latest.risk_score * 100,
                        2
                    ),
                    "risk_level": latest.risk_level,
                    "source": latest.source,
                    "model_version": latest.model_version,
                    "is_at_risk": bool(
                        snapshot.get("is_at_risk", False)
                    ),
                    "classification_threshold": (
                        snapshot.get("classification_threshold")
                    ),
                    "created_at": (
                        latest.created_at.isoformat()
                        if latest.created_at else None
                    ),
                }

            else:
                summary["unanalyzed_tasks"] += 1

            result_tasks.append({
                "id": task.id,
                "title": task.title,
                "priority": task.priority,
                "status": task.status,
                "deadline": (
                    task.deadline.isoformat()
                    if task.deadline else None
                ),
                "is_overdue": task.is_overdue(),
                "latest_prediction": prediction_data,
            })

        return {
            "summary": summary,
            "tasks": result_tasks,
            "notice": (
                "Random Forest навчений на синтетичних даних. "
                "Показники ризику є експериментальними та не "
                "є каліброваною ймовірністю для реальних користувачів."
            ),
        }
