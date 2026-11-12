
import re

from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Category
from app.repositories import CategoryRepository


class CategoryValidationError(ValueError):
    """Помилка перевірки категорії."""


class CategoryNotFoundError(LookupError):
    """Категорію не знайдено."""


class CategoryConflictError(ValueError):
    """Категорія з такою назвою вже існує."""


class CategoryService:
    """Бізнес-логіка управління категоріями."""

    ALLOWED_FIELDS = {
        "name",
        "description",
        "color",
    }

    def __init__(self, repository=None):
        self.repository = repository or CategoryRepository

    def _get_category(self, category_id, user_id):
        category = self.repository.get_by_id_for_user(
            category_id,
            user_id
        )

        if category is None:
            raise CategoryNotFoundError(
                "Категорію не знайдено."
            )

        return category

    def _validate(self, data, partial=False):
        if not isinstance(data, dict):
            raise CategoryValidationError(
                "Очікується JSON-об'єкт."
            )

        unknown = set(data) - self.ALLOWED_FIELDS

        if unknown:
            raise CategoryValidationError(
                "Невідомі поля категорії."
            )

        if not partial and "name" not in data:
            raise CategoryValidationError(
                "Назва категорії обов'язкова."
            )

        if "name" in data:
            name = data["name"]

            if not isinstance(name, str) or not name.strip():
                raise CategoryValidationError(
                    "Назва категорії не може бути порожньою."
                )

            if len(name.strip()) > 80:
                raise CategoryValidationError(
                    "Назва не повинна перевищувати 80 символів."
                )

            data["name"] = name.strip()

        if "description" in data:
            description = data["description"]

            if description is not None:
                if not isinstance(description, str):
                    raise CategoryValidationError(
                        "Опис повинен бути текстом."
                    )

                if len(description) > 255:
                    raise CategoryValidationError(
                        "Опис не повинен перевищувати 255 символів."
                    )

        if "color" in data:
            color = data["color"]

            if not isinstance(color, str) or not re.fullmatch(
                r"#[0-9A-Fa-f]{6}",
                color
            ):
                raise CategoryValidationError(
                    "Колір повинен мати формат HEX, наприклад #64748B."
                )

            data["color"] = color.upper()

        return data

    def create_category(self, user_id: int, data: dict):
        """Створює категорію."""

        data = self._validate(data.copy())

        if self.repository.get_by_name_for_user(
            data["name"],
            user_id
        ):
            raise CategoryConflictError(
                "Така категорія вже існує."
            )

        try:
            category = Category(
                user_id=user_id,
                name=data["name"],
                description=data.get("description"),
                color=data.get("color", "#64748B"),
            )

            self.repository.add(category)
            db.session.commit()

            return category

        except IntegrityError as error:
            db.session.rollback()

            raise CategoryConflictError(
                "Категорія з такою назвою вже існує."
            ) from error

        except Exception:
            db.session.rollback()
            raise

    def get_categories(self, user_id: int):
        """Отримує категорії поточного користувача."""

        return self.repository.get_by_user(user_id)

    def get_category(self, category_id: int, user_id: int):
        """Отримує конкретну категорію."""

        return self._get_category(category_id, user_id)

    def update_category(
        self,
        category_id: int,
        user_id: int,
        data: dict
    ):
        """Редагує категорію."""

        data = self._validate(
            data.copy(),
            partial=True
        )

        try:
            category = self._get_category(
                category_id,
                user_id
            )

            if (
                "name" in data
                and data["name"] != category.name
                and self.repository.get_by_name_for_user(
                    data["name"],
                    user_id
                )
            ):
                raise CategoryConflictError(
                    "Така категорія вже існує."
                )

            for field, value in data.items():
                setattr(category, field, value)

            if data:
                self.repository.update(category)
                db.session.commit()

            return category

        except IntegrityError as error:
            db.session.rollback()

            raise CategoryConflictError(
                "Категорія з такою назвою вже існує."
            ) from error

        except Exception:
            db.session.rollback()
            raise

    def delete_category(
        self,
        category_id: int,
        user_id: int
    ):
        """Видаляє категорію."""

        try:
            category = self._get_category(
                category_id,
                user_id
            )

            self.repository.delete(category)
            db.session.commit()

            return True

        except Exception:
            db.session.rollback()
            raise
