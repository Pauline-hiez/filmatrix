"""Fabrique de l'application Flask.

Ce module ne contient aucune route : il assemble. Les extensions viennent de
filmatrix.extensions, les routes de filmatrix.routes, et chacune est branchée
ici. Pour trouver une page, on ouvre le blueprint de son domaine.
"""

import os

from dotenv import load_dotenv
from flask import Flask, url_for

from filmatrix.extensions import db, login_manager, migrate, socketio
from filmatrix.models import User
from filmatrix.realtime.events import register_socket_events
from filmatrix.routes import (
    admin,
    auth,
    collection,
    friends,
    leaderboard,
    main,
    multiplayer,
    notifications,
    profile,
    quiz,
    shop,
)
from filmatrix.services.notifications import get_unread_count

load_dotenv()

# Chaque blueprint porte un domaine du site. L'ordre n'a pas d'importance :
# Flask les interroge par leurs règles d'URL, pas par leur rang.
BLUEPRINTS = (
    main.bp,
    auth.bp,
    profile.bp,
    quiz.bp,
    friends.bp,
    multiplayer.bp,
    shop.bp,
    leaderboard.bp,
    notifications.bp,
    admin.bp,
    collection.bp,
)


def resolve_database_uri(database_uri: str | None) -> str:
    """Choisit la base à utiliser, en normalisant l'URL fournie par l'hébergeur

    Certains hébergeurs annoncent encore leur base PostgreSQL en « postgres:// »,
    un préfixe que SQLAlchemy ne reconnaît plus.
    """
    if database_uri:
        return database_uri

    production_url = os.environ.get("DATABASE_URL")

    if production_url:
        return production_url.replace("postgres://", "postgresql://", 1)

    return "sqlite:///filmatrix.db"


def create_app(database_uri: str | None = None) -> Flask:
    """Construit et configure une instance de l'application Flask.

    Le paramètre database_uri permet de fournir une base différente
    (par exemple en mémoire, pour les tests) sans toucher à la vraie base.
    """
    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static",
    )

    app.config["SQLALCHEMY_DATABASE_URI"] = resolve_database_uri(database_uri)
    app.config["SECRET_KEY"] = os.environ["SECRET_KEY"]

    db.init_app(app)
    migrate.init_app(app, db)
    socketio.init_app(app, cors_allowed_origins="*", async_mode="gevent")
    register_socket_events(socketio)

    login_manager.init_app(app)
    login_manager.login_view = "auth.login"

    for blueprint in BLUEPRINTS:
        app.register_blueprint(blueprint)

    @login_manager.user_loader
    def load_user(user_id: str):
        """Indique à Flask-Login comment retrouver un utilisateur depuis son id de session"""
        return User.query.get(int(user_id))

    @app.template_filter("image_src")
    def image_src(value):
        """Réalise l'URL d'une image stockée en base.

        Les contenus uploadés sont enregistrés sous forme de chemin relatif
        (ex. uploads/characters/xxx.png) : il faut les préfixer par /static.
        Les URLs distantes (TMDB...) sont renvoyées telles quelles.
        """
        if not value:
            return ""
        if value.startswith("http://") or value.startswith("https://"):
            return value
        return url_for("static", filename=value)

    @app.context_processor
    def inject_notifications():
        """Rend le nombre de notifications non lues disponible dans tous les gabarits"""
        from flask_login import current_user

        if current_user.is_authenticated:
            return {"unread_notifications_count": get_unread_count(current_user.id)}

        return {"unread_notifications_count": 0}

    return app
