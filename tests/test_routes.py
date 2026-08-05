from src.database import db
from src.models import Question, User

"""Test des routes Flask principales"""

def test_home_returns_200(client):
    """La page d'accueil doit être accessble et répondre avec succès"""
    response = client.get("/")
    assert response.status_code == 200

def test_home_contains_title(client):
    """La page d'accueil doit contenir le nom du site"""
    response = client.get("/")
    assert b"Filmatrix" in response.data

def test_register_creates_account(client):
    """Une inscription avec des données valides doit créer un compte et rediriger"""
    response = client.post(
            "/inscription",
            data ={
                "username": "TestUser",
                "email": "test@filmatrix.fr",
                "password": "Azerty1!",
                },
                follow_redirects=True,
        )

    assert response.status_code == 200
    assert b"Se connecter" in response.data

def test_register_rejects_invalid_password(client):
    """Une inscription avec un mot de passe trop faible doit être refusée"""
    response = client.post(
            "/inscription",
            data={
                "username": "TestUser2",
                "email": "test2@filmatrix.fr",
                "password": "faible",
                },
        )
    assert b"ne respecte pas les r" in response.data

def create_user_and_login(client, app):
    """Crée un utilisateur de test et le connecte via le client de test"""
    with app.app_context():
        user = User(username="Joueur", email="joueur@filmatrix.fr")
        user.set_password("Azerty1!")
        db.session.add(user)
        db.session.commit()

    client.post(
            "/connexion",
            data={"email": "joueur@filmatrix.fr", "password": "Azerty1!"},
        )

def create_protected_question(app):
    """Crée une question réservée aux comptes, dans la base de test"""
    with app.app_context():
        question = Question(
                mode="qcm",
                category="test",
                difficulty="facile",
                prompt="Question protégée de test",
                payload={"options": ["A", "B"]},
                correct_answer={"index": 0},
                requires_account=True,
            )
        db.session.add(question)
        db.session.commit()

def test_protected_question_redirects_when_logged_out(client, app):
    """Un visiteur non connecté doit être redirigé vers la connexion"""
    create_protected_question(app)

    response = client.get("/quiz/qcm/1")

    assert response.status_code == 302
    assert "/connexion" in response.location

def test_protected_question_accessible_when_logged_in(client, app):
    """Un utilisateur connecté doit pouvoir accèder à la question protégée"""
    create_protected_question(app)
    create_user_and_login(client, app)

    response = client.get("/quiz/qcm/1")

    assert response.status_code == 200
    assert b"Question prot" in response.data
