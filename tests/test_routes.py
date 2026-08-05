from src.database import db 
from src.models import Question, User

"""Test des routes Flask principales"""

def test_accueil_repond_200(client):
    """La page d'accueil doit être accessble et répondre avec succès"""
    reponse = client.get("/")
    assert reponse.status_code == 200

def test_accueil_contient_le_titre(client):
    """La page d'accueil doit contenir le nom du site"""
    reponse = client.get("/")
    assert b"Filmatrix" in reponse.data

def test_inscription_cree_un_compte(client):
    """Une inscription avec des données valides doit créer un compte et rediriger"""
    reponse = client.post(
            "/inscription",
            data ={
                "username": "TestUser",
                "email": "test@filmatrix.fr",
                "password": "Azerty1!",
                },
                follow_redirects=True,
        )

    assert reponse.status_code == 200
    assert b"Se connecter" in reponse.data

def test_inscription_refuse_mot_de_passe_invalide(client):
    """Une inscription avec un mot de passe trop faible doit être refusée"""
    reponse = client.post(
            "/inscription",
            data={
                "username": "TestUser2",
                "email": "test2@filmatrix.fr",
                "password": "faible",
                },
        )
    assert b"ne respecte pas les r" in reponse.data

def creer_utilisateur_et_connecter(client, app):
    """Crée un utilisateur de test et le connecte via le client de test"""
    with app.app_context():
        utilisateur = User(username="Joueur", email="joueur@filmatrix.fr")
        utilisateur.set_password("Azerty1!")
        db.session.add(utilisateur)
        db.session.commit()

    client.post(
            "/connexion",
            data={"email": "joueur@filmatrix.fr", "password": "Azerty1!"},
        )

def creer_question_protegee(app):
    """Crée une question réservée aux comptes, dans la base de test"""
    with app.app_context():
        question = Question(
                mode="qcm",
                category="test",
                difficulty="facile",
                prompt="Question protégée de test",
                payload={"options": ["A", "B"]},
                correct_answer={"index": 0},
                necessite_compte=True,
            )
        db.session.add(question)
        db.session.commit()

def test_question_protegee_redirige_si_non_connecte(client, app):
    """Un visiteur non connecté doit être redirigé vers la connexion"""
    creer_question_protegee(app)

    reponse = client.get("/quiz/qcm/1")

    assert reponse.status_code == 302
    assert "/connexion" in reponse.location

def test_question_protegee_accessible_si_connecte(client, app):
    """Un utilisateur connecté doit pouvoir accèder à la question protégée"""
    creer_question_protegee(app)
    creer_utilisateur_et_connecter(client, app)

    reponse = client.get("/quiz/qcm/1")

    assert reponse.status_code == 200
    assert b"Question prot" in reponse.data