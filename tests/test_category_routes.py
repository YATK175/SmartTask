
from app import create_app
from app.extensions import db
from app.models import User, Category


class TestConfig:
    TESTING = True
    SECRET_KEY = "category-routes-test-secret"

    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SQLALCHEMY_ENGINE_OPTIONS = {
        "connect_args": {"check_same_thread": False}
    }


import pytest


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


def create_user(app, username, email):
    with app.app_context():
        user = User(username=username, email=email)
        user.set_password("TestPassword123")
        db.session.add(user)
        db.session.commit()
        return user.id


def create_category(app, user_id, name, color="#64748B"):
    with app.app_context():
        category = Category(
            user_id=user_id,
            name=name,
            color=color,
        )
        db.session.add(category)
        db.session.commit()
        return category.id


@pytest.fixture
def authenticated_client(app):
    user_id = create_user(
        app,
        "category_tester",
        "category@example.com",
    )

    client = app.test_client()

    response = client.post(
        "/api/auth/login",
        json={
            "email": "category@example.com",
            "password": "TestPassword123",
        },
    )

    assert response.status_code == 200

    return client, user_id


def category_payload(name="Learning", color="#64748B"):
    return {
        "name": name,
        "description": "Test category",
        "color": color,
    }


def test_category_routes_require_authentication(app):
    client = app.test_client()

    responses = [
        client.get("/api/categories"),
        client.post(
            "/api/categories",
            json=category_payload(),
        ),
        client.get("/api/categories/1"),
        client.patch(
            "/api/categories/1",
            json={"name": "Updated"},
        ),
        client.delete("/api/categories/1"),
    ]

    assert all(response.status_code == 401 for response in responses)


def test_get_categories_returns_only_current_users_categories(
    app,
    authenticated_client,
):
    client, user_id = authenticated_client

    create_category(app, user_id, "University")
    create_category(app, user_id, "Work")

    other_user_id = create_user(
        app,
        "another_category_user",
        "another_category@example.com",
    )

    create_category(app, other_user_id, "Foreign category")

    response = client.get("/api/categories")

    assert response.status_code == 200

    result = response.get_json()

    assert result["count"] == 2
    assert len(result["categories"]) == 2

    names = {
        item["name"]
        for item in result["categories"]
    }

    assert names == {"University", "Work"}

    assert all(
        item["user_id"] == user_id
        for item in result["categories"]
    )


def test_create_category_success(authenticated_client):
    client, user_id = authenticated_client

    response = client.post(
        "/api/categories",
        json=category_payload(
            name="  University  ",
            color="#aabbcc",
        ),
    )

    assert response.status_code == 201

    category = response.get_json()["category"]

    assert category["name"] == "University"
    assert category["color"] == "#AABBCC"
    assert category["description"] == "Test category"
    assert category["user_id"] == user_id


def test_create_category_uses_default_color(authenticated_client):
    client, _ = authenticated_client

    response = client.post(
        "/api/categories",
        json={"name": "Default color"},
    )

    assert response.status_code == 201
    assert response.get_json()["category"]["color"] == "#64748B"


def test_create_category_rejects_invalid_json(authenticated_client):
    client, _ = authenticated_client

    response = client.post(
        "/api/categories",
        data="{invalid json",
        content_type="application/json",
    )

    assert response.status_code == 400


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"name": ""},
        {"name": "   "},
        {"name": "A" * 81},
        {"name": "Valid", "description": 123},
        {"name": "Valid", "description": "A" * 256},
        {"name": "Valid", "color": "red"},
        {"name": "Valid", "color": "#12345"},
        {"name": "Valid", "unknown": "field"},
    ],
)
def test_create_category_rejects_invalid_data(
    authenticated_client,
    payload,
):
    client, _ = authenticated_client

    response = client.post(
        "/api/categories",
        json=payload,
    )

    assert response.status_code == 400
    assert "error" in response.get_json()


def test_create_duplicate_category_returns_409(
    authenticated_client,
):
    client, _ = authenticated_client

    first = client.post(
        "/api/categories",
        json=category_payload("University"),
    )

    assert first.status_code == 201

    second = client.post(
        "/api/categories",
        json=category_payload("University"),
    )

    assert second.status_code == 409
    assert "error" in second.get_json()


def test_same_category_name_allowed_for_different_users(
    app,
    authenticated_client,
):
    client, _ = authenticated_client

    first = client.post(
        "/api/categories",
        json=category_payload("Personal"),
    )

    assert first.status_code == 201

    other_user_id = create_user(
        app,
        "second_category_user",
        "second_category@example.com",
    )

    other_client = app.test_client()

    login_response = other_client.post(
        "/api/auth/login",
        json={
            "email": "second_category@example.com",
            "password": "TestPassword123",
        },
    )

    assert login_response.status_code == 200

    second = other_client.post(
        "/api/categories",
        json=category_payload("Personal"),
    )

    assert second.status_code == 201
    assert second.get_json()["category"]["user_id"] == other_user_id


def test_get_category_success(authenticated_client, app):
    client, user_id = authenticated_client

    category_id = create_category(
        app,
        user_id,
        "University",
    )

    response = client.get(
        f"/api/categories/{category_id}"
    )

    assert response.status_code == 200
    assert response.get_json()["category"]["name"] == "University"


def test_get_foreign_category_returns_404(
    app,
    authenticated_client,
):
    client, _ = authenticated_client

    other_user_id = create_user(
        app,
        "foreign_category_user",
        "foreign_category@example.com",
    )

    category_id = create_category(
        app,
        other_user_id,
        "Foreign",
    )

    response = client.get(
        f"/api/categories/{category_id}"
    )

    assert response.status_code == 404


def test_get_missing_category_returns_404(authenticated_client):
    client, _ = authenticated_client

    response = client.get("/api/categories/99999")

    assert response.status_code == 404


def test_update_category_success(authenticated_client, app):
    client, user_id = authenticated_client

    category_id = create_category(
        app,
        user_id,
        "Old name",
    )

    response = client.patch(
        f"/api/categories/{category_id}",
        json={
            "name": "New name",
            "color": "#abcdef",
        },
    )

    assert response.status_code == 200

    category = response.get_json()["category"]

    assert category["name"] == "New name"
    assert category["color"] == "#ABCDEF"


def test_update_category_accepts_partial_data(
    authenticated_client,
    app,
):
    client, user_id = authenticated_client

    category_id = create_category(
        app,
        user_id,
        "University",
    )

    response = client.patch(
        f"/api/categories/{category_id}",
        json={"description": "Updated description"},
    )

    assert response.status_code == 200

    category = response.get_json()["category"]

    assert category["name"] == "University"
    assert category["description"] == "Updated description"


def test_update_category_rejects_invalid_json(
    authenticated_client,
    app,
):
    client, user_id = authenticated_client

    category_id = create_category(
        app,
        user_id,
        "University",
    )

    response = client.patch(
        f"/api/categories/{category_id}",
        data="{invalid json",
        content_type="application/json",
    )

    assert response.status_code == 400


@pytest.mark.parametrize(
    "payload",
    [
        {"name": ""},
        {"name": "A" * 81},
        {"color": "invalid"},
        {"description": 123},
        {"unknown": "field"},
    ],
)
def test_update_category_rejects_invalid_data(
    authenticated_client,
    app,
    payload,
):
    client, user_id = authenticated_client

    category_id = create_category(
        app,
        user_id,
        "University",
    )

    response = client.patch(
        f"/api/categories/{category_id}",
        json=payload,
    )

    assert response.status_code == 400


def test_update_category_duplicate_name_returns_409(
    authenticated_client,
    app,
):
    client, user_id = authenticated_client

    first_id = create_category(
        app,
        user_id,
        "University",
    )

    create_category(
        app,
        user_id,
        "Work",
    )

    response = client.patch(
        f"/api/categories/{first_id}",
        json={"name": "Work"},
    )

    assert response.status_code == 409


def test_update_foreign_category_returns_404(
    app,
    authenticated_client,
):
    client, _ = authenticated_client

    other_user_id = create_user(
        app,
        "foreign_update_user",
        "foreign_update@example.com",
    )

    category_id = create_category(
        app,
        other_user_id,
        "Foreign category",
    )

    response = client.patch(
        f"/api/categories/{category_id}",
        json={"name": "Hacked"},
    )

    assert response.status_code == 404


def test_update_missing_category_returns_404(authenticated_client):
    client, _ = authenticated_client

    response = client.patch(
        "/api/categories/99999",
        json={"name": "Missing"},
    )

    assert response.status_code == 404


def test_delete_category_success_and_missing(
    authenticated_client,
    app,
):
    client, user_id = authenticated_client

    category_id = create_category(
        app,
        user_id,
        "Temporary",
    )

    response = client.delete(
        f"/api/categories/{category_id}"
    )

    assert response.status_code == 200

    missing_response = client.get(
        f"/api/categories/{category_id}"
    )

    assert missing_response.status_code == 404


def test_delete_foreign_category_returns_404(
    app,
    authenticated_client,
):
    client, _ = authenticated_client

    other_user_id = create_user(
        app,
        "foreign_delete_user",
        "foreign_delete@example.com",
    )

    category_id = create_category(
        app,
        other_user_id,
        "Foreign category",
    )

    response = client.delete(
        f"/api/categories/{category_id}"
    )

    assert response.status_code == 404


def test_delete_missing_category_returns_404(authenticated_client):
    client, _ = authenticated_client

    response = client.delete("/api/categories/99999")

    assert response.status_code == 404
