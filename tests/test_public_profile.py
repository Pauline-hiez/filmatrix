"""Tests du profil public : visibilité, bouton d'ami et pseudos cliquables."""

from filmatrix.services.badges import BADGES
from filmatrix.extensions import db
from filmatrix.models import Attempt, Friendship, Question, User


def create_player(app, username):
    """Crée un joueur avec un mot de passe connu"""
    with app.app_context():
        player = User(username=username, email=f"{username}@filmatrix.fr", total_xp=120)
        player.set_password("Azerty1!")
        db.session.add(player)
        db.session.commit()
        return player.id


def login(client, username):
    """Connecte le client de test sous ce pseudo"""
    return client.post(
        "/connexion",
        data={"email": f"{username}@filmatrix.fr", "password": "Azerty1!"},
    )


def link(app, requester_id, receiver_id, status):
    """Crée une relation d'amitié dans l'état demandé"""
    with app.app_context():
        db.session.add(
            Friendship(requester_id=requester_id, receiver_id=receiver_id, status=status)
        )
        db.session.commit()


def test_profile_of_a_stranger_is_visible_and_offers_to_add_them(client, app):
    """Un joueur non ami doit pouvoir consulter le profil et envoyer une demande"""
    me = create_player(app, "Moi")
    other = create_player(app, "Autre")
    login(client, "Moi")

    page = client.get(f"/joueur/{other}")

    assert page.status_code == 200
    assert "Ajouter un ami".encode() in page.data
    assert f'action="/amis/demander/{other}"'.encode() in page.data


def test_a_stranger_does_not_see_the_social_circle(client, app):
    """La liste d'amis et l'invitation à jouer restent réservées aux amis"""
    create_player(app, "Moi")
    other = create_player(app, "Autre")
    login(client, "Moi")

    page = client.get(f"/joueur/{other}")

    assert "Amis de".encode() not in page.data
    assert "Inviter à jouer".encode() not in page.data


def test_profile_shows_the_pending_request_already_sent(client, app):
    """Une demande déjà envoyée ne doit pas reproposer le bouton d'ajout"""
    me = create_player(app, "Moi")
    other = create_player(app, "Autre")
    link(app, me, other, "pending")
    login(client, "Moi")

    page = client.get(f"/joueur/{other}")

    assert "Demande d'ami envoyée".encode() in page.data
    assert "Ajouter un ami".encode() not in page.data


def test_profile_points_to_the_request_received(client, app):
    """Si l'autre joueur a déjà fait le premier pas, on renvoie vers la page Amis"""
    me = create_player(app, "Moi")
    other = create_player(app, "Autre")
    link(app, other, me, "pending")
    login(client, "Moi")

    page = client.get(f"/joueur/{other}")

    assert "demande d'ami".encode() in page.data
    assert b'href="/amis"' in page.data
    assert "Ajouter un ami".encode() not in page.data


def test_profile_of_a_friend_shows_everything(client, app):
    """Entre amis, le profil garde son contenu complet"""
    me = create_player(app, "Moi")
    other = create_player(app, "Autre")
    link(app, me, other, "accepted")
    login(client, "Moi")

    page = client.get(f"/joueur/{other}")

    assert "Vous êtes amis".encode() in page.data
    assert "Inviter à jouer".encode() in page.data
    assert "Amis de".encode() in page.data
    assert "Ajouter un ami".encode() not in page.data


def test_profile_lists_every_badge(client, app):
    """Tous les badges du jeu doivent apparaître, gagnés ou non"""
    create_player(app, "Moi")
    other = create_player(app, "Autre")
    login(client, "Moi")

    page = client.get(f"/joueur/{other}").get_data(as_text=True)

    for info in BADGES.values():
        assert info["name"] in page


def test_player_names_link_to_their_profile_once_logged_in(client, app):
    """Les pseudos du classement et de l'accueil doivent mener au profil"""
    create_player(app, "Moi")
    other = create_player(app, "Autre")

    with app.app_context():
        question = Question(
            mode="qcm",
            prompt="?",
            payload={"options": ["A", "B"]},
            correct_answer={"index": 0},
        )
        db.session.add(question)
        db.session.commit()
        db.session.add(Attempt(user_id=other, question_id=question.id, is_correct=True))
        db.session.commit()

    login(client, "Moi")

    assert f'/joueur/{other}'.encode() in client.get("/").data
    assert f'/joueur/{other}'.encode() in client.get("/classement").data


def test_player_names_are_not_links_for_a_visitor(client, app):
    """Un visiteur non connecté voit les pseudos, mais pas de lien vers un profil"""
    other = create_player(app, "Autre")

    home = client.get("/")

    assert home.status_code == 200
    assert b"/joueur/" not in home.data


def test_own_profile_lists_my_friends(client, app):
    """Mon propre profil doit afficher mes amis, comme celui des autres"""
    me = create_player(app, "Moi")
    other = create_player(app, "Autre")
    link(app, me, other, "accepted")
    login(client, "Moi")

    page = client.get("/profil")

    assert page.status_code == 200
    assert b"Autre" in page.data
    assert f'/joueur/{other}'.encode() in page.data


def test_own_profile_without_friends_invites_to_find_some(client, app):
    """Sans ami, le profil doit orienter le joueur plutôt qu'afficher un vide"""
    create_player(app, "Moi")
    login(client, "Moi")

    page = client.get("/profil")

    # L'apostrophe est échappée par Jinja : on vise la partie sans apostrophe.
    assert "Trouve des joueurs depuis le classement".encode() in page.data


def test_friends_sit_at_the_same_place_on_every_profile(client, app):
    """La section Amis doit tomber entre les badges et l'activité, sur les deux profils"""
    me = create_player(app, "Moi")
    other = create_player(app, "Autre")
    link(app, me, other, "accepted")
    login(client, "Moi")

    # On vise les titres de section : « Amis » tout court est aussi un lien de
    # la barre de navigation, présent bien plus haut dans la page.
    mine = client.get("/profil").get_data(as_text=True)
    assert mine.index(">Badges</h2>") < mine.index(">Amis</h2>") < mine.index(">Historique</h2>")

    theirs = client.get(f"/joueur/{other}").get_data(as_text=True)
    assert theirs.index(">Badges</h2>") < theirs.index("Amis de ") < theirs.index(">Activité par mode</h2>")


def test_a_friend_profile_offers_to_remove_them(client, app):
    """Le profil d'un ami doit proposer de le retirer"""
    me = create_player(app, "Moi")
    other = create_player(app, "Autre")
    link(app, me, other, "accepted")
    login(client, "Moi")

    page = client.get(f"/joueur/{other}")

    assert f'action="/amis/supprimer/{other}"'.encode() in page.data
    assert b"Retirer" in page.data


def test_a_stranger_profile_does_not_offer_to_remove_them(client, app):
    """Sans lien d'amitié, il n'y a rien à retirer"""
    create_player(app, "Moi")
    other = create_player(app, "Autre")
    login(client, "Moi")

    page = client.get(f"/joueur/{other}")

    assert f'action="/amis/supprimer/{other}"'.encode() not in page.data


def test_removing_a_friend_updates_both_profiles(client, app):
    """Après retrait, le profil repasse à l'état « pas encore amis » des deux côtés"""
    me = create_player(app, "Moi")
    other = create_player(app, "Autre")
    link(app, me, other, "accepted")
    login(client, "Moi")

    client.post(f"/amis/supprimer/{other}")

    page = client.get(f"/joueur/{other}")
    assert "Ajouter un ami".encode() in page.data
    assert "Vous êtes amis".encode() not in page.data

    # Et l'ancien ami ne me voit plus dans ses amis non plus.
    client.get("/deconnexion")
    login(client, "Autre")
    assert "Trouve des joueurs depuis le classement".encode() in client.get("/profil").data
