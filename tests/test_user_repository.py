
import pytest

from app import create_app
from app.extensions import db
from app.models import User
from app.repositories import UserRepository


class TestConfig:
    TESTING = True
    SECRET_KEY = "user-repository-test-secret"

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
                
@pytest.fixture(autouse=True)
def database_context(app):
    with app.app_context():
        yield


def create_user(username, email):
    user = User(
        username=username,
        email=email,
    )
    user.set_password("Password123")
    return user


def test_add_user():
    user = create_user(
        "repository_user",
        "repository@example.com",
    )

    result = UserRepository.add(user)

    assert result is user
    assert user.id is not None

    db.session.commit()


def test_get_by_id_returns_user():
    user = create_user(
        "id_user",
        "id@example.com",
    )

    db.session.add(user)
    db.session.commit()

    result = UserRepository.get_by_id(user.id)

    assert result is not None
    assert result.username == "id_user"


def test_get_by_id_returns_none_for_missing_user():
    result = UserRepository.get_by_id(99999)

    assert result is None


def test_get_by_email_normalizes_email():
    user = create_user(
        "email_user",
        "email@example.com",
    )

    db.session.add(user)
    db.session.commit()

    result = UserRepository.get_by_email(
        " EMAIL@EXAMPLE.COM "
    )

    assert result is not None
    assert result.id == user.id


def test_get_by_email_returns_none_for_missing_user():
    result = UserRepository.get_by_email(
        "missing@example.com"
    )

    assert result is None


def test_get_by_username_strips_whitespace():
    user = create_user(
        "username_user",
        "username@example.com",
    )

    db.session.add(user)
    db.session.commit()

    result = UserRepository.get_by_username(
        "  username_user  "
    )

    assert result is not None
    assert result.id == user.id


def test_get_by_username_returns_none_for_missing_user():
    result = UserRepository.get_by_username(
        "missing_user"
    )

    assert result is None
