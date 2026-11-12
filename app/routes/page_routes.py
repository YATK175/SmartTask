
from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
)
from flask_login import current_user


pages_bp = Blueprint("pages", __name__)


@pages_bp.get("/")
def index():
    """Головна сторінка."""

    if current_user.is_authenticated:
        return redirect(url_for("pages.dashboard"))

    return redirect(url_for("pages.login_page"))


@pages_bp.get("/login")
def login_page():
    """Сторінка авторизації."""

    if current_user.is_authenticated:
        return redirect(url_for("pages.dashboard"))

    return render_template("login.html")


@pages_bp.get("/register")
def register_page():
    """Сторінка реєстрації."""

    if current_user.is_authenticated:
        return redirect(url_for("pages.dashboard"))

    return render_template("register.html")


@pages_bp.get("/dashboard")
def dashboard():
    """Головна панель користувача."""

    if not current_user.is_authenticated:
        return redirect(url_for("pages.login_page"))

    return render_template(
        "dashboard.html",
        active_page="dashboard"
    )


@pages_bp.get("/tasks")
def tasks():
    """Сторінка управління завданнями."""

    if not current_user.is_authenticated:
        return redirect(url_for("pages.login_page"))

    return render_template(
        "tasks.html",
        active_page="tasks"
    )


@pages_bp.get("/categories")
def categories():
    """Сторінка управління категоріями."""

    if not current_user.is_authenticated:
        return redirect(url_for("pages.login_page"))

    return render_template(
        "categories.html",
        active_page="categories"
    )

@pages_bp.get("/ai-analytics")
def ai_analytics():
    """Сторінка інтелектуальної аналітики."""

    if not current_user.is_authenticated:
        return redirect(url_for("pages.login_page"))

    return render_template(
        "ai_analytics.html",
        active_page="ai_analytics"
    )
