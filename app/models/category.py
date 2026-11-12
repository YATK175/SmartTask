
from app.extensions import db


class Category(db.Model):
    """Модель категорії завдань."""

    __tablename__ = "categories"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )

    name = db.Column(
        db.String(80),
        nullable=False
    )

    description = db.Column(
        db.String(255),
        nullable=True
    )

    color = db.Column(
        db.String(7),
        nullable=False,
        default="#64748B"
    )

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        server_default=db.func.current_timestamp()
    )

    __table_args__ = (
        db.UniqueConstraint(
            "user_id",
            "name",
            name="uq_category_user_name"
        ),
        db.CheckConstraint(
            "length(trim(name)) > 0",
            name="ck_category_name"
        ),
    )

    user = db.relationship(
        "User",
        back_populates="categories"
    )

    tasks = db.relationship(
        "Task",
        back_populates="category",
        passive_deletes=True
    )

    def __repr__(self):
        return f"<Category {self.name}>"
