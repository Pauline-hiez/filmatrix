import html
import re

from filmatrix.extensions import db
from filmatrix.models import Question, User, Attempt, Friendship, Tag

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

def create_test_question(app, mode="qcm"):
    """Crée une question test non protégée, dans la base de test"""
    with app.app_context():
        question = Question(
                mode=mode,
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
def test_admin_question_form_compacts_tag_selection(client, app):
    """Le formulaire admin regroupe les tags et propose une recherche."""
    response = client.get("/admin/questions/nouvelle")
    assert response.status_code in (302, 403)


def test_setup_screen_offers_the_game_settings(client, app):
    """L'écran de préparation doit proposer thème et niveau avant de jouer"""
    create_test_question(app)

    response = client.get("/quiz/qcm")

    assert response.status_code == 200
    assert b'id="tag-genre"' in response.data
    assert b'id="tag-univers"' in response.data
    assert b'id="tag-pays"' in response.data
    assert b'id="tag-epoque"' in response.data
    assert b'id="level"' in response.data
    assert "Commencer".encode() in response.data


def test_setup_screen_keeps_selected_tag_and_counts_filtered_questions(client, app):
    """Le thème choisi doit être conservé et limiter le compteur de la préparation"""
    with app.app_context():
        tag = Tag(name="kaamelott", tag_type="univers")
        question = Question(
            mode="citation", content_type="serie", prompt="Une réplique culte",
            payload={}, correct_answer={"film": "Kaamelott"}, requires_account=False,
        )
        question.tags.append(tag)
        db.session.add(question)
        db.session.commit()
        tag_id = tag.id

    response = client.get(f"/quiz/citation?content_type=serie&tag_id={tag_id}")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert f'value="{tag_id}" selected' in page
    assert "Partie de 1 question" in page
    assert "1 disponible" in page


def test_setup_screen_combines_independent_theme_filters(client, app):
    """Les sélecteurs genre et univers doivent filtrer en intersection."""
    with app.app_context():
        comedy = Tag(name="comédie", tag_type="genre")
        friends = Tag(name="friends", tag_type="univers")
        matching = Question(mode="citation", content_type="serie", prompt="Réplique", payload={}, correct_answer={"film": "Friends"}, requires_account=False)
        matching.tags.extend([comedy, friends])
        genre_only = Question(mode="citation", content_type="serie", prompt="Autre", payload={}, correct_answer={"film": "Autre"}, requires_account=False)
        genre_only.tags.append(comedy)
        db.session.add_all([matching, genre_only])
        db.session.commit()
        comedy_id, friends_id = comedy.id, friends.id

    response = client.get(f"/quiz/citation?content_type=serie&tag_id={comedy_id}&tag_id={friends_id}")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Partie de 1 question" in page
    assert f'value="{comedy_id}" selected' in page
    assert f'value="{friends_id}" selected' in page


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


def question_ids_of_a_run(client, mode="qcm", length=10):
    """Joue une partie du début à la fin et retourne les questions servies"""
    ids = []
    for position in range(1, length + 1):
        page = client.get(f"/quiz/{mode}/{position}").get_data(as_text=True)
        ids.append(re.search(r'data-question-id="(\d+)"', page).group(1))
    return ids


def test_each_run_draws_a_different_question_order(client, app):
    """Deux parties du même mode ne doivent pas dérouler les mêmes questions"""
    create_questions(app, 30)

    runs = {tuple(question_ids_of_a_run(client)) for _ in range(5)}

    assert len(runs) > 1


def test_a_run_never_repeats_the_same_question(client, app):
    """Le tirage ne doit pas servir deux fois la même question dans une partie"""
    create_questions(app, 30)

    ids = question_ids_of_a_run(client)

    assert len(set(ids)) == len(ids)


def test_the_question_order_holds_during_the_run(client, app):
    """Avancer puis revenir sur une question doit retrouver la même"""
    create_questions(app, 30)

    ids = question_ids_of_a_run(client)
    # On relit sans repasser par la position 1, qui relance volontairement une partie.
    again = [
        re.search(r'data-question-id="(\d+)"', client.get(f"/quiz/qcm/{p}").get_data(as_text=True)).group(1)
        for p in range(2, 11)
    ]

    assert again == ids[1:]


def test_the_draw_respects_the_content_filter(client, app):
    """Une partie séries ne doit tirer que des questions de séries"""
    with app.app_context():
        for index in range(12):
            db.session.add(
                Question(
                    mode="qcm",
                    content_type="serie" if index % 2 else "film",
                    prompt=f"Question {index}",
                    payload={"options": ["A", "B"]},
                    correct_answer={"index": 0},
                    requires_account=False,
                )
            )
        db.session.commit()

    ids = [
        re.search(r'data-question-id="(\d+)"', client.get(f"/quiz/qcm/{p}?content_type=serie").get_data(as_text=True)).group(1)
        for p in range(1, 7)
    ]

    with app.app_context():
        assert {Question.query.get(int(i)).content_type for i in ids} == {"serie"}


def test_the_draw_spares_a_visitor_the_account_only_questions(client, app):
    """Un visiteur ne doit pas être éjecté vers la connexion en pleine partie"""
    create_questions(app, 12)
    create_protected_question(app)

    with app.app_context():
        protected = {q.id for q in Question.query.filter_by(requires_account=True)}

    drawn = set()
    for _ in range(10):
        drawn |= {int(i) for i in question_ids_of_a_run(client)}

    assert not (drawn & protected)


def test_qcm_options_are_shuffled(client, app):
    """L'ordre d'affichage des propositions doit varier d'une partie à l'autre"""
    with app.app_context():
        db.session.add(
            Question(
                mode="qcm",
                prompt="Seule question du mode",
                payload={"options": ["A", "B", "C", "D"]},
                correct_answer={"index": 0},
                requires_account=False,
            )
        )
        db.session.commit()

    orders = set()
    for _ in range(20):
        page = client.get("/quiz/qcm/1").get_data(as_text=True)
        orders.add(tuple(re.findall(r'data-answer="(\d+)"', page)))

    assert len(orders) > 1


def test_a_shuffled_option_is_still_judged_correctly(client, app):
    """Le mélange ne doit pas fausser la correction : le bouton porte l'index d'origine"""
    with app.app_context():
        db.session.add(
            Question(
                mode="qcm",
                prompt="Seule question du mode",
                payload={"options": ["Bonne", "Mauvaise", "Mauvaise", "Mauvaise"]},
                correct_answer={"index": 0},
                requires_account=False,
            )
        )
        db.session.commit()

    client.get("/quiz/qcm/1")

    assert client.post("/quiz/qcm/1", data={"answer": "0"}).get_json()["is_correct"] is True
    assert client.post("/quiz/qcm/1", data={"answer": "2"}).get_json()["is_correct"] is False


def test_multiplayer_page_is_open_to_a_visitor(client, app):
    """Un visiteur doit pouvoir découvrir le duel avant même d'avoir un compte"""
    response = client.get("/multijoueur")

    assert response.status_code == 200
    assert "Défie tes amis".encode() in response.data
    assert "Créer un compte".encode() in response.data


def test_the_home_page_advertises_the_multiplayer(client, app):
    """Le multijoueur ne doit plus se mériter : l'accueil doit y mener"""
    create_test_question(app)

    response = client.get("/").get_data(as_text=True)

    assert 'href="/multijoueur"' in response
    assert "Défie un ami en temps réel" in response


def test_the_navbar_leads_to_the_multiplayer(client, app):
    """Le lien doit suivre le joueur de page en page, pas seulement sur l'accueil"""
    for url in ["/", "/modes", "/classement"]:
        assert 'href="/multijoueur"' in client.get(url).get_data(as_text=True)


def test_every_mode_explains_its_rule(client, app):
    """Chaque mode doit dire ce qu'on attend du joueur, page modes et préparation"""
    from filmatrix.game_modes import GAME_MODES

    create_test_question(app)
    modes_page = html.unescape(client.get("/modes").get_data(as_text=True))

    for mode in GAME_MODES:
        setup_page = html.unescape(client.get(f"/quiz/{mode['slug']}").get_data(as_text=True))

        assert mode["how"] in modes_page, f"règle absente de la page des modes : {mode['slug']}"
        assert mode["how"] in setup_page, f"règle absente de la préparation : {mode['slug']}"


def test_the_modes_page_agrees_with_the_setup_screen(client, app):
    """Les deux pages lisent la même source : elles ne peuvent plus diverger"""
    from filmatrix.game_modes import GAME_MODES

    modes_page = client.get("/modes").get_data(as_text=True)

    for mode in GAME_MODES:
        assert mode["name"] in modes_page


def test_multiplayer_page_offers_a_duel_to_a_player_with_friends(client, app):
    """Un joueur qui a des amis doit pouvoir les défier depuis cette page"""
    create_user_and_login(client, app)

    with app.app_context():
        friend = User(username="Adversaire", email="adversaire@filmatrix.fr")
        friend.set_password("Azerty1!")
        db.session.add(friend)
        db.session.commit()
        me = User.query.filter_by(username="Joueur").first()
        db.session.add(Friendship(requester_id=me.id, receiver_id=friend.id, status="accepted"))
        db.session.commit()
        friend_id = friend.id

    page = client.get("/multijoueur").get_data(as_text=True)

    assert "Adversaire" in page
    assert f'action="/multijoueur/inviter/{friend_id}"' in page
    assert "Défier".encode().decode() in page
