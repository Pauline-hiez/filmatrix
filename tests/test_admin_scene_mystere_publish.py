"""Tests de la publication d'un cas Scène Mystère depuis sa ligne dans la liste
admin (filmatrix/routes/admin_special_games.py:admin_scene_mystere_publish).

Les fonctions réseau de filmatrix/services/prod_sync.py sont mockées : aucun
test existant dans ce projet ne se connecte à une vraie base de production,
et publish_mystery_cases/find_publishable_mystery_cases ouvrent une connexion
psycopg2 réelle."""

from unittest.mock import patch

from filmatrix.extensions import db
from filmatrix.models import MysteryCase, User


def create_admin(username: str = "AdminMystere", email: str = "adminmystere@filmatrix.fr") -> User:
    admin = User(username=username, email=email, is_admin=True)
    admin.set_password("Azerty1!")
    db.session.add(admin)
    db.session.commit()
    return admin


def login_admin(client, email: str = "adminmystere@filmatrix.fr") -> None:
    client.post("/connexion", data={"email": email, "password": "Azerty1!"})


def create_case(image_url: str = "https://example.com/scene.jpg") -> MysteryCase:
    case = MysteryCase(image_url=image_url)
    db.session.add(case)
    db.session.commit()
    return case


PATCH_PREFIX = "filmatrix.routes.admin_special_games"


def test_publish_button_inserts_the_case_when_still_publishable(client, app):
    """Un cas encore absent de la prod doit être publié et le confirmer."""
    with app.app_context():
        create_admin()
        case = create_case()
        case_id = case.id

    login_admin(client)

    with patch(f"{PATCH_PREFIX}.is_local_environment", return_value=True), \
         patch(f"{PATCH_PREFIX}.find_publishable_mystery_cases", return_value=[case]) as find_mock, \
         patch(f"{PATCH_PREFIX}.publish_mystery_cases", return_value={"inserted": [{"local_id": case_id, "prod_id": 1}]}) as publish_mock:
        response = client.post(
            f"/admin/jeux-speciaux/scene-mystere/{case_id}/publier", follow_redirects=True
        )

    assert response.status_code == 200
    assert "Scène publiée en production.".encode() in response.data
    # find_publishable_mystery_cases est aussi rappelée par la page liste après
    # la redirection (pour ses propres boutons) : au moins un appel suffit ici.
    find_mock.assert_called()
    publish_mock.assert_called_once_with([case_id])


def test_publish_button_does_not_duplicate_an_already_published_case(client, app):
    """Un cas déjà présent en prod ne doit jamais être réinséré (pas de doublon
    silencieux à un second clic, publish_mystery_cases() ne dédoublonne pas
    elle-même)."""
    with app.app_context():
        create_admin()
        case = create_case()
        case_id = case.id

    login_admin(client)

    with patch(f"{PATCH_PREFIX}.is_local_environment", return_value=True), \
         patch(f"{PATCH_PREFIX}.find_publishable_mystery_cases", return_value=[]), \
         patch(f"{PATCH_PREFIX}.publish_mystery_cases") as publish_mock:
        response = client.post(
            f"/admin/jeux-speciaux/scene-mystere/{case_id}/publier", follow_redirects=True
        )

    assert response.status_code == 200
    assert "Cette scène est déjà publiée en production.".encode() in response.data
    publish_mock.assert_not_called()


def test_publish_button_is_unavailable_outside_local_environment(client, app):
    """Publier la prod depuis la prod elle-même n'a pas de sens (même garde
    que la page centralisée) : accès direct à l'URL bloqué."""
    with app.app_context():
        create_admin()
        case = create_case()
        case_id = case.id

    login_admin(client)

    with patch(f"{PATCH_PREFIX}.is_local_environment", return_value=False):
        response = client.post(f"/admin/jeux-speciaux/scene-mystere/{case_id}/publier")

    assert response.status_code == 404


def test_list_shows_check_failed_rather_than_a_false_published_status(client, app):
    """Si la connexion à la prod échoue au chargement de la liste, ça doit se
    voir comme un échec de vérification, jamais comme un "Publié" trompeur
    (régression : une exception avalée en silence retombait sur un ensemble
    vide, indiscernable d'un cas réellement déjà publié)."""
    with app.app_context():
        create_admin()
        create_case()

    login_admin(client)

    with patch(f"{PATCH_PREFIX}.is_local_environment", return_value=True), \
         patch(f"{PATCH_PREFIX}.find_publishable_mystery_cases", side_effect=RuntimeError("connexion refusée")):
        response = client.get("/admin/jeux-speciaux/scene-mystere")

    assert response.status_code == 200
    assert "Vérification impossible".encode() in response.data
    assert "Publié".encode() not in response.data
