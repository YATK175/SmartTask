
import re

from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import User
from app.repositories import UserRepository


class AuthValidationError(ValueError):
    """Помилка перевірки реєстраційних даних."""


class AuthConflictError(ValueError):
    """Конфлікт унікальності користувача."""


class AuthService:
    """Бізнес-логіка реєстрації та авторизації."""

    def __init__(self, user_repository=None):
        self.user_repository = (
            user_repository or UserRepository
        )

    def register_user(
        self,
        username: str,
        email: str,
        password: str
    ):
        """Реєструє нового користувача."""

        if not all(
            isinstance(value, str)
            for value in (username, email, password)
        ):
            raise AuthValidationError(
                "Усі поля повинні містити текст."
            )

        username = username.strip()
        email = email.strip().lower()

        if not 3 <= len(username) <= 50:
            raise AuthValidationError(
                "Ім'я користувача повинно містити від 3 до 50 символів."
            )

        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            raise AuthValidationError(
                "Некоректний формат електронної пошти."
            )

        if len(email) > 255:
            raise AuthValidationError(
                "Email занадто довгий."
            )

        if len(password) < 8:
            raise AuthValidationError(
                "Пароль повинен містити щонайменше 8 символів."
            )

        if len(password) > 128:
            raise AuthValidationError(
                "Пароль не повинен перевищувати 128 символів."
            )

        if self.user_repository.get_by_username(username):
            raise AuthConflictError(
                "Це ім'я користувача вже зайняте."
            )

        if self.user_repository.get_by_email(email):
            raise AuthConflictError(
                "Користувач із таким email вже існує."
            )

        try:
            user = User(
                username=username,
                email=email
            )

            user.set_password(password)

            self.user_repository.add(user)
            db.session.commit()

            return user

        except IntegrityError as error:
            db.session.rollback()

            raise AuthConflictError(
                "Користувач із такими даними вже існує."
            ) from error

        except Exception:
            db.session.rollback()
            raise

    def authenticate(self, email: str, password: str):
        """Перевіряє облікові дані користувача."""

        if not isinstance(email, str) or not isinstance(password, str):
            return None

        user = self.user_repository.get_by_email(email)

        if user is None:
            return None

        if not user.is_active:
            return None

        if not user.check_password(password):
            return None

        return user
