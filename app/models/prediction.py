
import json

from app.extensions import db


class Prediction(db.Model):
    """Модель результату прогнозування ризику."""

    __tablename__ = "predictions"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    task_id = db.Column(
        db.Integer,
        db.ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False
    )

    risk_score = db.Column(
        db.Float,
        nullable=False
    )

    risk_level = db.Column(
        db.String(10),
        nullable=False
    )

    source = db.Column(
        db.String(10),
        nullable=False
    )

    model_version = db.Column(
        db.String(50),
        nullable=True
    )

    features_snapshot = db.Column(
        db.Text,
        nullable=False,
        default="{}"
    )

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        server_default=db.func.current_timestamp()
    )

    __table_args__ = (
        db.CheckConstraint(
            "risk_score >= 0.0 AND risk_score <= 1.0",
            name="ck_prediction_score"
        ),
        db.CheckConstraint(
            "risk_level IN ('LOW', 'MEDIUM', 'HIGH')",
            name="ck_prediction_level"
        ),
        db.CheckConstraint(
            "source IN ('ML', 'FALLBACK')",
            name="ck_prediction_source"
        ),
        db.CheckConstraint(
            "(source = 'ML' AND model_version IS NOT NULL) "
            "OR source = 'FALLBACK'",
            name="ck_prediction_model_version"
        ),
    )

    task = db.relationship(
        "Task",
        back_populates="predictions"
    )

    def set_features(self, features: dict) -> None:
        """Зберігає характеристики прогнозування."""

        self.features_snapshot = json.dumps(
            features,
            ensure_ascii=False
        )

    def get_features(self) -> dict:
        """Повертає характеристики прогнозування."""

        try:
            return json.loads(self.features_snapshot)
        except (TypeError, json.JSONDecodeError):
            return {}

    def __repr__(self):
        return f"<Prediction {self.risk_level}: {self.risk_score}>"
