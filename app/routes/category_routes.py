
from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.services.category_service import (
    CategoryService,
    CategoryValidationError,
    CategoryNotFoundError,
    CategoryConflictError,
)


category_bp = Blueprint(
    "categories",
    __name__,
    url_prefix="/api/categories"
)

category_service = CategoryService()


def serialize_category(category):
    return {
        "id": category.id,
        "user_id": category.user_id,
        "name": category.name,
        "description": category.description,
        "color": category.color,
        "created_at": (
            category.created_at.isoformat()
            if category.created_at else None
        ),
    }


@category_bp.get("")
@login_required
def get_categories():
    categories = category_service.get_categories(
        current_user.id
    )

    return jsonify({
        "count": len(categories),
        "categories": [
            serialize_category(category)
            for category in categories
        ]
    }), 200


@category_bp.post("")
@login_required
def create_category():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "error": "Очікується JSON-об'єкт."
        }), 400

    try:
        category = category_service.create_category(
            current_user.id,
            data
        )

        return jsonify({
            "message": "Категорію створено.",
            "category": serialize_category(category)
        }), 201

    except CategoryValidationError as error:
        return jsonify({"error": str(error)}), 400

    except CategoryConflictError as error:
        return jsonify({"error": str(error)}), 409


@category_bp.get("/<int:category_id>")
@login_required
def get_category(category_id):
    try:
        category = category_service.get_category(
            category_id,
            current_user.id
        )

        return jsonify({
            "category": serialize_category(category)
        }), 200

    except CategoryNotFoundError as error:
        return jsonify({"error": str(error)}), 404


@category_bp.patch("/<int:category_id>")
@login_required
def update_category(category_id):
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "error": "Очікується JSON-об'єкт."
        }), 400

    try:
        category = category_service.update_category(
            category_id,
            current_user.id,
            data
        )

        return jsonify({
            "message": "Категорію оновлено.",
            "category": serialize_category(category)
        }), 200

    except CategoryValidationError as error:
        return jsonify({"error": str(error)}), 400

    except CategoryConflictError as error:
        return jsonify({"error": str(error)}), 409

    except CategoryNotFoundError as error:
        return jsonify({"error": str(error)}), 404


@category_bp.delete("/<int:category_id>")
@login_required
def delete_category(category_id):
    try:
        category_service.delete_category(
            category_id,
            current_user.id
        )

        return jsonify({
            "message": "Категорію видалено."
        }), 200

    except CategoryNotFoundError as error:
        return jsonify({"error": str(error)}), 404
