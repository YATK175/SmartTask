
from datetime import datetime, timezone

from app.extensions import db


class Task(db.Model):
    """Модель завдання."""

    __tablename__ = "tasks"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )

    category_id = db.Column(
        db.Integer,
        db.ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True
    )

    title = db.Column(
        db.String(200),
        nullable=False
    )

    description = db.Column(
        db.Text,
        nullable=True
    )

    priority = db.Column(
        db.String(10),
        nullable=False,
        default="MEDIUM"
    )

    status = db.Column(
        db.String(20),
        nullable=False,
        default="NEW"
    )

    deadline = db.Column(
        db.DateTime,
        nullable=False
    )

    estimated_duration_minutes = db.Column(
        db.Integer,
        nullable=False,
        default=60
    )

    actual_duration_minutes = db.Column(
        db.Integer,
        nullable=True
    )

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        server_default=db.func.current_timestamp()
    )

    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        server_default=db.func.current_timestamp(),
        onupdate=db.func.current_timestamp()
    )

    completed_at = db.Column(
        db.DateTime,
        nullable=True
    )

    __table_args__ = (
        db.CheckConstraint(
            "priority IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')",
            name="ck_task_priority"
        ),
        db.CheckConstraint(
            "status IN ('NEW', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED')",
            name="ck_task_status"
        ),
        db.CheckConstraint(
            "estimated_duration_minutes > 0",
            name="ck_task_estimated_duration"
        ),
        db.CheckConstraint(
            "actual_duration_minutes IS NULL OR actual_duration_minutes >= 0",
            name="ck_task_actual_duration"
        ),
        db.CheckConstraint(
            "length(trim(title)) > 0",
            name="ck_task_title"
        ),
        db.CheckConstraint(
            "(status = 'COMPLETED' AND completed_at IS NOT NULL) OR "
            "(status <> 'COMPLETED' AND completed_at IS NULL)",
            name="ck_task_completed_at"
        ),
    )

    user = db.relationship(
        "User",
        back_populates="tasks"
    )

    category = db.relationship(
        "Category",
        back_populates="tasks"
    )

    history = db.relationship(
        "TaskHistory",
        back_populates="task",
        cascade="all, delete-orphan",
        passive_deletes=True
    )

    predictions = db.relationship(
        "Prediction",
        back_populates="task",
        cascade="all, delete-orphan",
        passive_deletes=True
    )

    def is_overdue(self) -> bool:
        """Перевіряє, чи прострочено завдання."""

        if self.status in ("COMPLETED", "CANCELLED"):
            return False

        deadline = self.deadline

        if deadline.tzinfo is not None:
            deadline = deadline.astimezone(
                timezone.utc
            ).replace(tzinfo=None)

        now = datetime.now(timezone.utc).replace(tzinfo=None)

        return deadline < now

    def update_status(self, new_status: str) -> None:
        """Змінює статус завдання."""

        allowed_statuses = {
            "NEW",
            "IN_PROGRESS",
            "COMPLETED",
            "CANCELLED"
        }

        if new_status not in allowed_statuses:
            raise ValueError("Недопустимий статус завдання.")

        self.status = new_status

        if new_status == "COMPLETED":
            self.completed_at = (
                datetime.now(timezone.utc).replace(tzinfo=None)
            )
        else:
            self.completed_at = None

    def __repr__(self):
        return f"<Task {self.title}>"
