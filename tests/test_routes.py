from src.database import db
from src.models import Question, User, Attempt

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

def create_test_question(app, difficulty="facile", mode="qcm"):
    """Crée une question test non protégée, dans la base de test"""
    with app.app_context():
        question = Question(
                mode=mode,
                category="test",
                difficulty=difficulty,
                prompt="Question de test XP",
                payload={"option": 0},
                correct_answer={"index": 0},
                requires_account=False,
            )
        db.session.add(question)
        db.session.commit()

def test_xp_awarded_only_once_per_question(client, app):
    """L'XP ne doit être gagnée qu'à la première bonne réponse d'une question donnée"""
    create_test_question(app, difficulty="facile")
    create_user_and_login(client, app)

    client.post("/quiz/qcm/1", data={"answer": "0"})

    with app.app_context():
        user = User.query.filter_by(username="Joueur").first()
        xp_after_first_answer = user.total_xp

    client.post("/quiz/qcm/1", data={"answer": 0})

    with app.app_context():
        user = User.query.filter_by(username="Joueur").first()
        xp_after_second_answer = user.total_xp

    assert xp_after_first_answer == 10
    assert xp_after_second_answer == 10

def test_leaderboard_shows_all_players_sorted_by_xp(client, app):
    """Le classement doit afficher tous les joueurs, triés de plus d'XP au moins"""
    with app.app_context():
        player_low = User(username="JoueurBas", email="bas@filmatrix.fr", total_xp=10)
        player_low.set_password("Azerty1!")

        player_high = User(username="JoueurHaut", email="haut@filmatrix.fr", total_xp=100)
        player_high.set_password("Azerty1!")

        db.session.add(player_low)
        db.session.add(player_high)
        db.session.commit()

        question = Question(
                mode="qcm",
                category="test",
                difficulty="facile",
                prompt="Question de test classement",
                payload={"options": ["A", "B"]},
                correct_answer={"index": 0},
                requires_account=False,
            )
        db.session.add(question)
        db.session.commit()

        attempt_low = Attempt(user_id=player_low.id, question_id=question.id, is_correct=True)
        attempt_high = Attempt(user_id=player_high.id, question_id=question.id, is_correct=True)
        db.session.add(attempt_low)
        db.session.add(attempt_high)
        db.session.commit()

    response = client.get("/classement")

    assert response.status_code == 200
    page_text = response.data.decode("utf-8")
    position_high = page_text.find("JoueurHaut")
    position_low = page_text.find("JoueurBas")

    assert position_high != -1
    assert position_low != -1
    assert position_high < position_low