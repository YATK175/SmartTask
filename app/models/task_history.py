
from app.extensions import db


class TaskHistory(db.Model):
    """Історія змін завдань."""

    __tablename__ = "task_history"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    task_id = db.Column(
        db.Integer,
        db.ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False
    )

    changed_by_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )

    event_type = db.Column(
        db.String(30),
        nullable=False
    )

    old_status = db.Column(
        db.String(20),
        nullable=True
    )

    new_status = db.Column(
        db.String(20),
        nullable=True
    )

    old_deadline = db.Column(
        db.DateTime,
        nullable=True
    )

    new_deadline = db.Column(
        db.DateTime,
        nullable=True
    )

    note = db.Column(
        db.Text,
        nullable=True
    )

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        server_default=db.func.current_timestamp()
    )

    __table_args__ = (
        db.CheckConstraint(
            "event_type IN "
            "('CREATED', 'STATUS_CHANGED', 'DEADLINE_CHANGED', 'UPDATED')",
            name="ck_history_event_type"
        ),
    )

    task = db.relationship(
        "Task",
        back_populates="history"
    )

    changed_by = db.relationship(
        "User",
        foreign_keys=[changed_by_user_id]
    )

    def __repr__(self):
        return f"<TaskHistory {self.id}: {self.event_type}>"
