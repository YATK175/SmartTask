
import pytest

from sqlalchemy.exc import IntegrityError

from app import create_app
from app.extensions import db
from app.models import User, Category
from app.repositories import CategoryRepository
from app.services.category_service import (
    CategoryService,
    CategoryValidationError,
    CategoryNotFoundError,
    CategoryConflictError,
)


class TestConfig:
    TESTING = True
    SECRET_KEY = "category-service-test-secret"

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
def category_context(app):
    with app.app_context():
        user = User(
            username="category_service_user",
            email="category_service@example.com",
        )

        user.set_password("TestPassword123")

        db.session.add(user)
        db.session.commit()

        yield user.id


def test_validate_normalizes_category_data():
    service = CategoryService()

    data = service._validate({
        "name": "  University  ",
        "description": "Test",
        "color": "#aabbcc",
    })

    assert data["name"] == "University"
    assert data["color"] == "#AABBCC"


def test_validate_rejects_non_dictionary():
    service = CategoryService()

    with pytest.raises(CategoryValidationError):
        service._validate("invalid")


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"unknown": "value"},
        {"name": ""},
        {"name": "   "},
        {"name": "A" * 81},
        {"name": "Valid", "description": 123},
        {"name": "Valid", "description": "A" * 256},
        {"name": "Valid", "color": "red"},
        {"name": "Valid", "color": "#12345"},
        {"name": "Valid", "color": 123},
    ],
)
def test_validate_rejects_invalid_category_data(data):
    service = CategoryService()

    with pytest.raises(CategoryValidationError):
        service._validate(data)


def test_validate_allows_partial_update():
    service = CategoryService()

    data = service._validate(
        {"description": "Updated"},
        partial=True,
    )

    assert data == {"description": "Updated"}


def test_create_category_success(category_context):
    service = CategoryService()

    category = service.create_category(
        category_context,
        {
            "name": "University",
            "description": "Study tasks",
            "color": "#123abc",
        },
    )

    assert category.id is not None
    assert category.user_id == category_context
    assert category.name == "University"
    assert category.color == "#123ABC"


def test_create_category_uses_default_color(category_context):
    service = CategoryService()

    category = service.create_category(
        category_context,
        {"name": "Personal"},
    )

    assert category.color == "#64748B"


def test_create_duplicate_category_raises_conflict(category_context):
    service = CategoryService()

    service.create_category(
        category_context,
        {"name": "University"},
    )

    with pytest.raises(CategoryConflictError):
        service.create_category(
            category_context,
            {"name": "University"},
        )


def test_same_name_allowed_for_different_users(app, category_context):
    service = CategoryService()

    other_user = User(
        username="other_service_user",
        email="other_service@example.com",
    )
    other_user.set_password("TestPassword123")

    db.session.add(other_user)
    db.session.commit()

    service.create_category(
        category_context,
        {"name": "Personal"},
    )

    category = service.create_category(
        other_user.id,
        {"name": "Personal"},
    )

    assert category.user_id == other_user.id


def test_create_integrity_error_becomes_conflict(
    category_context,
    monkeypatch,
):
    service = CategoryService()

    def fail_add(category):
        raise IntegrityError(
            "INSERT INTO categories",
            {},
            RuntimeError("Duplicate category"),
        )

    monkeypatch.setattr(
        CategoryRepository,
        "add",
        staticmethod(fail_add),
    )

    with pytest.raises(CategoryConflictError):
        service.create_category(
            category_context,
            {"name": "University"},
        )


def test_get_categories_returns_user_categories(category_context):
    service = CategoryService()

    service.create_category(
        category_context,
        {"name": "University"},
    )

    service.create_category(
        category_context,
        {"name": "Work"},
    )

    categories = service.get_categories(category_context)

    assert len(categories) == 2
    assert {item.name for item in categories} == {
        "University",
        "Work",
    }


def test_get_category_success(category_context):
    service = CategoryService()

    created = service.create_category(
        category_context,
        {"name": "University"},
    )

    category = service.get_category(
        created.id,
        category_context,
    )

    assert category.id == created.id


def test_get_foreign_category_raises_not_found(
    app,
    category_context,
):
    service = CategoryService()

    category = service.create_category(
        category_context,
        {"name": "University"},
    )

    other_user = User(
        username="foreign_service_user",
        email="foreign_service@example.com",
    )
    other_user.set_password("TestPassword123")

    db.session.add(other_user)
    db.session.commit()

    with pytest.raises(CategoryNotFoundError):
        service.get_category(
            category.id,
            other_user.id,
        )


def test_update_category_success(category_context):
    service = CategoryService()

    category = service.create_category(
        category_context,
        {"name": "University"},
    )

    updated = service.update_category(
        category.id,
        category_context,
        {
            "name": "Education",
            "color": "#abcdef",
        },
    )

    assert updated.name == "Education"
    assert updated.color == "#ABCDEF"


def test_update_category_partial_description(category_context):
    service = CategoryService()

    category = service.create_category(
        category_context,
        {"name": "University"},
    )

    updated = service.update_category(
        category.id,
        category_context,
        {"description": "New description"},
    )

    assert updated.name == "University"
    assert updated.description == "New description"


def test_update_category_with_empty_data(category_context):
    service = CategoryService()

    category = service.create_category(
        category_context,
        {"name": "University"},
    )

    updated = service.update_category(
        category.id,
        category_context,
        {},
    )

    assert updated.id == category.id
    assert updated.name == "University"


def test_update_category_with_same_name(category_context):
    service = CategoryService()

    category = service.create_category(
        category_context,
        {"name": "University"},
    )

    updated = service.update_category(
        category.id,
        category_context,
        {"name": "University"},
    )

    assert updated.name == "University"


def test_update_category_duplicate_raises_conflict(category_context):
    service = CategoryService()

    first = service.create_category(
        category_context,
        {"name": "University"},
    )

    service.create_category(
        category_context,
        {"name": "Work"},
    )

    with pytest.raises(CategoryConflictError):
        service.update_category(
            first.id,
            category_context,
            {"name": "Work"},
        )


def test_update_integrity_error_becomes_conflict(
    category_context,
    monkeypatch,
):
    service = CategoryService()

    category = service.create_category(
        category_context,
        {"name": "University"},
    )

    def fail_update(category):
        raise IntegrityError(
            "UPDATE categories",
            {},
            RuntimeError("Unique constraint"),
        )

    monkeypatch.setattr(
        CategoryRepository,
        "update",
        staticmethod(fail_update),
    )

    with pytest.raises(CategoryConflictError):
        service.update_category(
            category.id,
            category_context,
            {"color": "#123456"},
        )


def test_update_missing_category_raises_not_found(category_context):
    service = CategoryService()

    with pytest.raises(CategoryNotFoundError):
        service.update_category(
            99999,
            category_context,
            {"name": "Missing"},
        )


def test_delete_category_success(category_context):
    service = CategoryService()

    category = service.create_category(
        category_context,
        {"name": "Temporary"},
    )

    result = service.delete_category(
        category.id,
        category_context,
    )

    assert result is True

    with pytest.raises(CategoryNotFoundError):
        service.get_category(
            category.id,
            category_context,
        )


def test_delete_missing_category_raises_not_found(category_context):
    service = CategoryService()

    with pytest.raises(CategoryNotFoundError):
        service.delete_category(
            99999,
            category_context,
        )
