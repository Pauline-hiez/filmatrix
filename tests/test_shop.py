"""Tests du système de boutique (pièces et titres)"""

from src.database import db 
from src.models import User 
from src.shop import owns_title, purchase_title

def create_test_user(coins: int = 0) -> User:
    """Crée un utilisateur de test avec un solde de pièces donné"""
    user = User(username="ShopTester", email="shop@filmatrix.fr", coins=coins)
    user.set_password("Azerty1!")
    db.session.add(user)
    db.session.commit()
    return user 

def test_purchase_succeeds_with_enough_coins(app):
    """Si l'utilisateur possède assez de pièces, l'achat doit réussir"""
    with app.app_context():
        user = create_test_user(coins=100)

        success = purchase_title(user, "cinephile")
        db.session.commit()

        assert success is True
        assert owns_title(user, "cinephile") is True
        assert user.coins == 50

def test_purchase_fails_without_enough_coins(app):
    """Si l'utilisateur n'a pas assez de pièces, l'achat doit échouer"""
    with app.app_context():
        user = create_test_user(coins=10)

        success = purchase_title(user, "cinephile")
        db.session.commit()

        assert success is False
        assert owns_title(user, "cinephile") is False
        assert user.coins == 10

def test_purchase_fails_if_already_owned(app):
    """L'achat doit échouer si l'utilisateur possède déja le titre"""
    with app.app_context():
        user = create_test_user(coins=200)

        purchase_title(user, "cinephile")
        db.session.commit()

        coins_after_first_purchase = user.coins

        success = purchase_title(user, "cinephile")
        db.session.commit()

        assert success is False
        assert user.coins == coins_after_first_purchase

def test_purchase_fails_for_unknow_title(app):
    """L'achat doit échouer si un titre donné n'existe pas"""
    with app.app_context():
        user = create_test_user(coins=1000)

        success = purchase_title(user, "titre_qui_n_existe_pas")

        assert success is False