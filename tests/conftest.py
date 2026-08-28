"""Configuration partagée pour les tests : app Flask et client de test."""

import pytest

from filmatrix import create_app
from filmatrix.extensions import db


@pytest.fixture
def app():
    """Fournit une application Flask entièrement séparée, avec une base en mémoire."""
    flask_app = create_app("sqlite:///:memory:")

    with flask_app.app_context():
        db.create_all()
        yield flask_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Fournit un client de test, capable de simuler des requêtes HTTP."""
    return app.test_client()