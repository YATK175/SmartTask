
from flask import Blueprint, jsonify, request
from flask_login import (
    current_user,
    login_required,
    login_user,
    logout_user,
)

from app.services.auth_service import (
    AuthService,
    AuthValidationError,
    AuthConflictError,
)


auth_bp = Blueprint(
    "auth",
    __name__,
    url_prefix="/api/auth"
)

auth_service = AuthService()


def user_to_dict(user):
    """Формує безпечне представлення користувача."""

    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "created_at": user.created_at.isoformat()
        if user.created_at else None
    }


@auth_bp.post("/register")
def register():
    """Реєстрація користувача."""

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "error": "Очікується JSON-об'єкт."
        }), 400

    try:
        user = auth_service.register_user(
            username=data.get("username"),
            email=data.get("email"),
            password=data.get("password")
        )

        login_user(user)

        return jsonify({
            "message": "Реєстрація успішна.",
            "user": user_to_dict(user)
        }), 201

    except AuthValidationError as error:
        return jsonify({"error": str(error)}), 400

    except AuthConflictError as error:
        return jsonify({"error": str(error)}), 409


@auth_bp.post("/login")
def login():
    """Авторизація користувача."""

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "error": "Очікується JSON-об'єкт."
        }), 400

    user = auth_service.authenticate(
        data.get("email"),
        data.get("password")
    )

    if user is None:
        return jsonify({
            "error": "Неправильний email або пароль."
        }), 401

    login_user(user)

    return jsonify({
        "message": "Авторизація успішна.",
        "user": user_to_dict(user)
    }), 200


@auth_bp.post("/logout")
@login_required
def logout():
    """Вихід із системи."""

    logout_user()

    return jsonify({
        "message": "Ви вийшли із системи."
    }), 200


@auth_bp.get("/me")
@login_required
def me():
    """Отримання інформації про поточного користувача."""

    return jsonify({
        "user": user_to_dict(current_user)
    }), 200
