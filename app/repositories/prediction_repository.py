
from app.extensions import db
from app.models import Prediction, Task


class PredictionRepository:
    """Репозиторій для збереження результатів ML-прогнозування."""

    @staticmethod
    def add(prediction: Prediction):
        """Додає прогноз до поточної транзакції."""

        db.session.add(prediction)
        db.session.flush()

        return prediction

    @staticmethod
    def get_by_task_for_user(task_id: int, user_id: int):
        """Отримує історію прогнозів конкретного завдання."""

        statement = (
            db.select(Prediction)
            .join(Task, Prediction.task_id == Task.id)
            .where(
                Task.id == task_id,
                Task.user_id == user_id
            )
            .order_by(
                Prediction.created_at.desc(),
                Prediction.id.desc()
            )
        )

        return db.session.scalars(statement).all()

    @staticmethod
    def get_latest_for_task(task_id: int, user_id: int):
        """Отримує останній прогноз завдання."""

        statement = (
            db.select(Prediction)
            .join(Task, Prediction.task_id == Task.id)
            .where(
                Task.id == task_id,
                Task.user_id == user_id
            )
            .order_by(
                Prediction.created_at.desc(),
                Prediction.id.desc()
            )
            .limit(1)
        )

        return db.session.scalar(statement)
    @staticmethod
    def get_all_for_user(user_id: int):
        """Отримує всі прогнози завдань конкретного користувача."""

        statement = (
            db.select(Prediction)
            .join(Task, Prediction.task_id == Task.id)
            .where(Task.user_id == user_id)
            .order_by(
                Prediction.created_at.desc(),
                Prediction.id.desc()
            )
        )

        return db.session.scalars(statement).all()
