
import pytest

from app import create_app
from app.extensions import db
from app.routes import auth_routes


class TestConfig:
    TESTING = True
    SECRET_KEY = "test-secret-key"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "connect_args": {"check_same_thread": False}
    }


@pytest.fixture
def app():
    app = create_app(config_class=TestConfig)

    with app.app_context():
        db.drop_all()
        db.create_all()

    yield app

    with app.app_context():
        db.session.remove()
        db.drop_all()
        db.engine.dispose()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def existing_user():
    return {
        "username": "existing_user",
        "email": "existing@example.com",
        "password": "Password123",
    }


def make_register_payload(**overrides):
    data = {
        "username": "new_user",
        "email": "new@example.com",
        "password": "Password123",
    }
    data.update(overrides)
    return data


def create_existing_user(app, data):
    """Створює тестового користувача в контексті Flask."""
    with app.app_context():
        user = auth_routes.auth_service.register_user(
            username=data["username"],
            email=data["email"],
            password=data["password"],
        )
        return user.id


# --------------------------------------------------
# REGISTER
# --------------------------------------------------


def test_register_success_and_automatic_login(app, client):
    response = client.post(
        "/api/auth/register",
        json=make_register_payload(),
    )

    assert response.status_code == 201

    result = response.get_json()

    assert result is not None
    assert "user" in result
    assert result["user"]["username"] == "new_user"
    assert result["user"]["email"] == "new@example.com"
    assert "password" not in result["user"]

    # Після реєстрації користувач має бути авторизований.
    me_response = client.get("/api/auth/me")

    assert me_response.status_code == 200


def test_register_rejects_invalid_json(client):
    response = client.post(
        "/api/auth/register",
        data="{invalid json",
        content_type="application/json",
    )

    assert response.status_code == 400


def test_register_rejects_missing_fields(client):
    response = client.post(
        "/api/auth/register",
        json={},
    )

    assert response.status_code == 400


def test_register_rejects_invalid_email(client):
    response = client.post(
        "/api/auth/register",
        json=make_register_payload(
            email="invalid-email",
        ),
    )

    assert response.status_code == 400


def test_register_rejects_short_password(client):
    response = client.post(
        "/api/auth/register",
        json=make_register_payload(
            password="123",
        ),
    )

    assert response.status_code == 400


def test_register_duplicate_username_returns_409(
    app, client, existing_user
):
    create_existing_user(app, existing_user)

    response = client.post(
        "/api/auth/register",
        json=make_register_payload(
            username=existing_user["username"],
            email="another@example.com",
        ),
    )

    assert response.status_code == 409


def test_register_duplicate_email_returns_409(
    app, client, existing_user
):
    create_existing_user(app, existing_user)

    response = client.post(
        "/api/auth/register",
        json=make_register_payload(
            username="another_user",
            email=existing_user["email"],
        ),
    )

    assert response.status_code == 409


# --------------------------------------------------
# LOGIN
# --------------------------------------------------


def test_login_success(app, client, existing_user):
    user_id = create_existing_user(app, existing_user)

    response = client.post(
        "/api/auth/login",
        json={
            "email": existing_user["email"],
            "password": existing_user["password"],
        },
    )

    assert response.status_code == 200

    result = response.get_json()

    assert result is not None
    assert "user" in result
    assert result["user"]["id"] == user_id
    assert result["user"]["email"] == existing_user["email"]
    assert "password" not in result["user"]


def test_login_rejects_invalid_json(client):
    response = client.post(
        "/api/auth/login",
        data="{invalid json",
        content_type="application/json",
    )

    assert response.status_code == 400


@pytest.mark.parametrize(
    "email,password",
    [
        ("unknown@example.com", "Password123"),
        ("existing@example.com", "WrongPassword"),
        (None, "Password123"),
        ("existing@example.com", None),
    ],
)
def test_login_rejects_invalid_credentials(
    app,
    client,
    existing_user,
    email,
    password,
):
    create_existing_user(app, existing_user)

    response = client.post(
        "/api/auth/login",
        json={
            "email": email,
            "password": password,
        },
    )

    assert response.status_code == 401


# --------------------------------------------------
# LOGOUT
# --------------------------------------------------


def test_logout_requires_authentication(client):
    response = client.post("/api/auth/logout")

    assert response.status_code == 401


def test_logout_success_and_invalidates_session(
    app, client, existing_user
):
    create_existing_user(app, existing_user)

    # Спочатку авторизуємо користувача.
    login_response = client.post(
        "/api/auth/login",
        json={
            "email": existing_user["email"],
            "password": existing_user["password"],
        },
    )

    assert login_response.status_code == 200

    # Виконуємо вихід.
    logout_response = client.post("/api/auth/logout")

    assert logout_response.status_code == 200

    # Після виходу доступ до профілю має бути заборонений.
    me_response = client.get("/api/auth/me")

    assert me_response.status_code == 401


# --------------------------------------------------
# CURRENT USER
# --------------------------------------------------


def test_me_requires_authentication(client):
    response = client.get("/api/auth/me")

    assert response.status_code == 401


def test_me_returns_authenticated_user(app, client, existing_user):
    user_id = create_existing_user(app, existing_user)

    # Авторизуємо користувача.
    login_response = client.post(
        "/api/auth/login",
        json={
            "email": existing_user["email"],
            "password": existing_user["password"],
        },
    )

    assert login_response.status_code == 200

    # Отримуємо інформацію про поточного користувача.
    response = client.get("/api/auth/me")

    assert response.status_code == 200

    result = response.get_json()

    assert result is not None
    assert "user" in result
    assert result["user"]["id"] == user_id
    assert result["user"]["username"] == existing_user["username"]
    assert result["user"]["email"] == existing_user["email"]
    assert "password" not in result["user"]
