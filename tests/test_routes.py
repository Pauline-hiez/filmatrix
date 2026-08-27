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
    create_test_question(app)
    create_user_and_login(client, app)

    # L'XP dépend désormais du niveau choisi par le joueur, porté par l'URL.
    client.post("/quiz/qcm/1?level=facile", data={"answer": "0"})

    with app.app_context():
        user = User.query.filter_by(username="Joueur").first()
        xp_after_first_answer = user.total_xp

    client.post("/quiz/qcm/1?level=facile", data={"answer": 0})

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

def create_and_login_user_with_coins(client, app, coins: int = 100):
    """Crée un utilisateur de test avec un solde de pièces donné, et le connecte"""
    with app.app_context():
        user = User(username="Acheteur", email="acheteur@filmatrix.fr", coins=coins)
        user.set_password("Azerty1!")
        db.session.add(user)
        db.session.commit()

    client.post(
        "/connexion",
        data={"email": "acheteur@filmatrix.fr", "password": "Azerty1!"},
    )


def test_buy_title_route_succeeds_with_enough_coins(client, app):
    """La route d'achat doit reussir et deduire les pieces si le solde est suffisant"""
    create_and_login_user_with_coins(client, app, coins=100)

    response = client.post(
        "/boutique/acheter/cinephile",
        follow_redirects=True,
    )

    assert response.status_code == 200

    with app.app_context():
        user = User.query.filter_by(username="Acheteur").first()
        assert user.coins == 50


def test_equip_title_route_updates_equipped_title(client, app):
    """La route d'equipement doit mettre a jour le titre affiche pour l'utilisateur"""
    create_and_login_user_with_coins(client, app, coins=100)
    client.post("/boutique/acheter/cinephile")

    response = client.post(
        "/boutique/equiper/cinephile",
        follow_redirects=True,
    )

    assert response.status_code == 200

    with app.app_context():
        user = User.query.filter_by(username="Acheteur").first()
        assert user.equipped_title == "cinephile"


def test_equip_title_route_fails_if_not_owned(client, app):
    """La route d'equipement doit refuser un titre non possede"""
    create_and_login_user_with_coins(client, app, coins=0)

    client.post("/boutique/equiper/cinephile", follow_redirects=True)

    with app.app_context():
        user = User.query.filter_by(username="Acheteur").first()
        assert user.equipped_title is None
def test_setup_screen_offers_the_game_settings(client, app):
    """L'écran de préparation doit proposer catégorie, thème et niveau avant de jouer"""
    create_test_question(app)

    response = client.get("/quiz/qcm")

    assert response.status_code == 200
    assert b'id="category"' in response.data
    assert b'id="tag"' in response.data
    assert b'id="level"' in response.data
    assert "Commencer".encode() in response.data


def test_setup_screen_refuses_to_start_a_mode_without_questions(client, app):
    """Un mode vide doit afficher un bouton désactivé plutôt qu'une partie sans question"""
    create_test_question(app, mode="qcm")

    response = client.get("/quiz/blindtest")

    assert response.status_code == 200
    assert "Aucune question disponible".encode() in response.data


def test_setup_screen_redirects_for_an_unknown_mode(client, app):
    """Un mode inexistant dans l'URL doit ramener au catalogue des modes"""
    response = client.get("/quiz/nawak")

    assert response.status_code == 302
    assert "/modes" in response.location


def test_mode_cards_lead_to_the_setup_screen(client, app):
    """Les cartes de l'accueil ne doivent plus lancer la partie directement"""
    create_test_question(app)

    response = client.get("/")

    assert b'href="/quiz/qcm"' in response.data
    assert b'href="/quiz/qcm/1"' not in response.data


def create_questions(app, count, mode="qcm"):
    """Crée plusieurs questions jouables dans un mode, dans la base de test"""
    with app.app_context():
        for number in range(count):
            db.session.add(
                Question(
                    mode=mode,
                    category="test",
                    difficulty="facile",
                    prompt=f"Question de test {number}",
                    payload={"options": ["A", "B"]},
                    correct_answer={"index": 0},
                    requires_account=False,
                )
            )
        db.session.commit()


def test_quiz_shows_progress_within_the_run(client, app):
    """Chaque question doit indiquer où en est le joueur et ce qu'il lui reste"""
    create_questions(app, 12)

    response = client.get("/quiz/qcm/3")

    assert response.status_code == 200
    assert "Question 3".encode() in response.data
    assert b"/ 10" in response.data
    assert "Encore 7 questions".encode() in response.data


def test_quiz_run_stops_after_ten_questions(client, app):
    """Au-delà de la dixième question, la partie doit s'achever même s'il en reste en base"""
    create_questions(app, 12)

    assert client.get("/quiz/qcm/10").status_code == 200

    response = client.get("/quiz/qcm/11")

    assert response.status_code == 200
    assert "terminé".encode() in response.data


def test_quiz_progress_follows_a_short_mode(client, app):
    """Un mode qui compte moins de dix questions annonce son vrai total"""
    create_questions(app, 3, mode="citation")

    response = client.get("/quiz/citation/1")

    assert response.status_code == 200
    assert b"/ 3" in response.data
    assert "Encore 2 questions".encode() in response.data


def test_quiz_progress_announces_the_last_question(client, app):
    """La dernière question doit être annoncée comme telle, sans reste à zéro"""
    create_questions(app, 3, mode="citation")

    response = client.get("/quiz/citation/3")

    assert response.status_code == 200
    assert "Dernière question".encode() in response.data


def test_setup_screen_announces_the_run_length(client, app):
    """L'écran de préparation doit annoncer la longueur d'une partie"""
    create_questions(app, 12)

    response = client.get("/quiz/qcm")

    assert response.status_code == 200
    assert "Partie de 10 questions".encode() in response.data
    assert "12 disponibles".encode() in response.data
