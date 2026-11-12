
import pytest
from sqlalchemy.exc import IntegrityError

from app import create_app
from app.extensions import db
from app.models import User
from app.repositories import UserRepository
from app.services.auth_service import (
    AuthService,
    AuthValidationError,
    AuthConflictError,
)


class TestConfig:
    TESTING = True
    SECRET_KEY = "auth-service-test-secret"

    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SQLALCHEMY_ENGINE_OPTIONS = {
        "connect_args": {"check_same_thread": False}
    }


@pytest.fixture
def app():
    application = create_app(TestConfig)

    try:
        with application.app_context():
            db.drop_all()
            db.create_all()

        yield application

    finally:
        with application.app_context():
            db.session.remove()
            try:
                db.drop_all()
            finally:
                db.engine.dispose()


@pytest.fixture
def auth_service(app):
    with app.app_context():
        yield AuthService()


def test_register_user_success_and_normalizes_data(auth_service):
    user = auth_service.register_user(
        username="  test_user  ",
        email="  TEST@EXAMPLE.COM  ",
        password="Password123",
    )

    assert user.id is not None
    assert user.username == "test_user"
    assert user.email == "test@example.com"
    assert user.check_password("Password123")
    assert not user.check_password("WrongPassword")


@pytest.mark.parametrize(
    "username,email,password",
    [
        (None, "test@example.com", "Password123"),
        ("test_user", None, "Password123"),
        ("test_user", "test@example.com", None),
        (123, "test@example.com", "Password123"),
        ("test_user", 123, "Password123"),
        ("test_user", "test@example.com", 123),
    ],
)
def test_register_rejects_non_string_fields(
    auth_service,
    username,
    email,
    password,
):
    with pytest.raises(AuthValidationError):
        auth_service.register_user(
            username,
            email,
            password,
        )


@pytest.mark.parametrize(
    "username",
    [
        "",
        "ab",
        "   ",
        "u" * 51,
    ],
)
def test_register_rejects_invalid_username(
    auth_service,
    username,
):
    with pytest.raises(AuthValidationError):
        auth_service.register_user(
            username,
            "test@example.com",
            "Password123",
        )


@pytest.mark.parametrize(
    "email",
    [
        "",
        "invalid-email",
        "user@",
        "@example.com",
        "user example@example.com",
    ],
)
def test_register_rejects_invalid_email(
    auth_service,
    email,
):
    with pytest.raises(AuthValidationError):
        auth_service.register_user(
            "test_user",
            email,
            "Password123",
        )


def test_register_rejects_email_longer_than_255(auth_service):
    email = ("a" * 245) + "@example.com"

    with pytest.raises(AuthValidationError):
        auth_service.register_user(
            "test_user",
            email,
            "Password123",
        )


@pytest.mark.parametrize(
    "password",
    [
        "",
        "1234567",
        "a" * 129,
    ],
)
def test_register_rejects_invalid_password(
    auth_service,
    password,
):
    with pytest.raises(AuthValidationError):
        auth_service.register_user(
            "test_user",
            "test@example.com",
            password,
        )


def test_register_rejects_duplicate_username(auth_service):
    auth_service.register_user(
        "existing_user",
        "first@example.com",
        "Password123",
    )

    with pytest.raises(AuthConflictError):
        auth_service.register_user(
            "existing_user",
            "second@example.com",
            "Password123",
        )


def test_register_rejects_duplicate_email_case_insensitive(
    auth_service,
):
    auth_service.register_user(
        "first_user",
        "TEST@example.com",
        "Password123",
    )

    with pytest.raises(AuthConflictError):
        auth_service.register_user(
            "second_user",
            " test@EXAMPLE.com ",
            "Password123",
        )


def test_register_integrity_error_becomes_conflict(
    auth_service,
    monkeypatch,
):
    def fail_add(user):
        raise IntegrityError(
            "INSERT INTO users",
            {},
            RuntimeError("Unique constraint"),
        )

    monkeypatch.setattr(
        UserRepository,
        "add",
        staticmethod(fail_add),
    )

    with pytest.raises(AuthConflictError):
        auth_service.register_user(
            "race_user",
            "race@example.com",
            "Password123",
        )


def test_register_rolls_back_on_unexpected_error(
    auth_service,
    monkeypatch,
):
    def fail_add(user):
        raise RuntimeError("Unexpected repository error")

    monkeypatch.setattr(
        UserRepository,
        "add",
        staticmethod(fail_add),
    )

    with pytest.raises(RuntimeError):
        auth_service.register_user(
            "error_user",
            "error@example.com",
            "Password123",
        )

    assert db.session.is_active


def test_authenticate_success(auth_service):
    auth_service.register_user(
        "login_user",
        "login@example.com",
        "Password123",
    )

    user = auth_service.authenticate(
        "login@example.com",
        "Password123",
    )

    assert user is not None
    assert user.username == "login_user"


def test_authenticate_normalizes_email(auth_service):
    auth_service.register_user(
        "normalized_user",
        "user@example.com",
        "Password123",
    )

    user = auth_service.authenticate(
        " USER@EXAMPLE.COM ",
        "Password123",
    )

    assert user is not None
    assert user.email == "user@example.com"


def test_authenticate_wrong_password_returns_none(auth_service):
    auth_service.register_user(
        "wrong_password_user",
        "wrong@example.com",
        "Password123",
    )

    result = auth_service.authenticate(
        "wrong@example.com",
        "WrongPassword123",
    )

    assert result is None


def test_authenticate_unknown_email_returns_none(auth_service):
    result = auth_service.authenticate(
        "unknown@example.com",
        "Password123",
    )

    assert result is None


@pytest.mark.parametrize(
    "email,password",
    [
        (None, "Password123"),
        ("user@example.com", None),
        (123, "Password123"),
        ("user@example.com", 123),
    ],
)
def test_authenticate_rejects_non_string_values(
    auth_service,
    email,
    password,
):
    result = auth_service.authenticate(email, password)

    assert result is None


def test_authenticate_inactive_user_returns_none():
    class InactiveUser:
        is_active = False

        def check_password(self, password):
            return True

    class FakeRepository:
        @staticmethod
        def get_by_email(email):
            return InactiveUser()

    service = AuthService(user_repository=FakeRepository)

    result = service.authenticate(
        "inactive@example.com",
        "Password123",
    )

    assert result is None
