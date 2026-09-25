"""Tests du déroulé de Scène Mystère : le joueur doit pouvoir cliquer les
zones dans n'importe quel ordre (il n'y a pas de décoy, cf. MysteryZone),
alors qu'un bug faisait échouer tout clic hors d'un ordre caché imposé côté
serveur (filmatrix/routes/special_games.py:scene_mystere_click)."""

from filmatrix.extensions import db
from filmatrix.models import MysteryAnswer, MysteryCase, MysteryZone, User


def create_player(username: str = "Joueur", email: str = "joueur@filmatrix.fr", golden_tickets: int = 5) -> User:
    user = User(username=username, email=email, golden_tickets=golden_tickets)
    user.set_password("Azerty1!")
    db.session.add(user)
    db.session.commit()
    return user


def login(client, email: str = "joueur@filmatrix.fr") -> None:
    client.post("/connexion", data={"email": email, "password": "Azerty1!"})


def create_case_with_zones(zone_count: int = 3) -> MysteryCase:
    """Crée un cas jouable avec zone_count zones, chacune avec une réponse
    acceptée distincte ("Film 0", "Film 1"...)."""
    case = MysteryCase(image_url="https://example.com/scene.jpg", time_limit_seconds=240)
    db.session.add(case)
    db.session.commit()

    for index in range(zone_count):
        zone = MysteryZone(
            case_id=case.id, pos_x=index * 10, pos_y=index * 10, width=10, height=10, order_index=index
        )
        db.session.add(zone)
        db.session.commit()
        db.session.add(MysteryAnswer(zone_id=zone.id, text=f"Film {index}", order_index=0))
    db.session.commit()
    return case


def test_clicking_a_zone_out_of_the_hidden_order_still_succeeds(client, app):
    """Cliquer la DERNIÈRE zone (order_index le plus haut) en premier doit
    quand même être accepté : il n'y a pas d'ordre imposé au joueur."""
    with app.app_context():
        create_player()
        case = create_case_with_zones(3)
        case_id = case.id
        last_zone_id = (
            MysteryZone.query.filter_by(case_id=case.id).order_by(MysteryZone.order_index.desc()).first().id
        )

    login(client)
    client.post(f"/jeux-speciaux/scene-mystere/commencer/{case_id}")

    response = client.post("/jeux-speciaux/scene-mystere/clic", json={"zone_id": last_zone_id})

    assert response.status_code == 200
    assert response.get_json()["correct"] is True


def test_all_zones_can_be_resolved_in_reverse_order(client, app):
    """Le joueur doit pouvoir résoudre toutes les zones d'un cas en partant
    de la dernière vers la première, sans jamais essuyer un faux "raté"."""
    with app.app_context():
        create_player()
        case = create_case_with_zones(3)
        case_id = case.id
        zones = MysteryZone.query.filter_by(case_id=case.id).order_by(MysteryZone.order_index.desc()).all()
        zone_ids = [zone.id for zone in zones]
        answers = {zone.id: MysteryAnswer.query.filter_by(zone_id=zone.id).first().text for zone in zones}

    login(client)
    client.post(f"/jeux-speciaux/scene-mystere/commencer/{case_id}")

    for zone_id in zone_ids:
        click_response = client.post("/jeux-speciaux/scene-mystere/clic", json={"zone_id": zone_id})
        assert click_response.get_json()["correct"] is True, f"zone {zone_id} refusée"

        answer_response = client.post(
            "/jeux-speciaux/scene-mystere/repondre", json={"guess": answers[zone_id]}
        )
        data = answer_response.get_json()
        assert data["correct"] is True

    assert data["done"] is True
    assert data["found_count"] == 3


def test_a_zone_cannot_be_clicked_twice(client, app):
    """Une zone déjà résolue (bonne ou mauvaise réponse) ne doit plus être
    acceptée sur un second clic, même si la partie n'est pas terminée (une
    autre zone reste à résoudre)."""
    with app.app_context():
        create_player()
        case = create_case_with_zones(2)
        case_id = case.id
        zones = MysteryZone.query.filter_by(case_id=case.id).order_by(MysteryZone.order_index).all()
        zone_id = zones[0].id
        correct_answer = MysteryAnswer.query.filter_by(zone_id=zone_id).first().text

    login(client)
    client.post(f"/jeux-speciaux/scene-mystere/commencer/{case_id}")

    client.post("/jeux-speciaux/scene-mystere/clic", json={"zone_id": zone_id})
    client.post("/jeux-speciaux/scene-mystere/repondre", json={"guess": correct_answer})

    second_click = client.post("/jeux-speciaux/scene-mystere/clic", json={"zone_id": zone_id})

    assert second_click.get_json()["correct"] is False
