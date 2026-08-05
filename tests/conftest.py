"""Configuration partagée pour les tests : app Flask et client de test"""
import pytest

from app import app as flask_app
from src.database import db 

@pytest.fixture
def app():
    """Fournit l'application Flask configurée avec une base de test en mémoire"""
    flask_app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    flask_app.config["TESTING"] = True 

    with flask_app.app_context():
        db.create_all()
        yield flask_app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    """Fournit un client de test, capable de simuler des requêtes HTTP"""
    return app.test_client()