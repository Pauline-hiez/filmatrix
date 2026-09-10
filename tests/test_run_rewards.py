"""Tests de la finalisation groupée des récompenses d'une partie solo :
rien n'est gagné tant que la partie n'est pas terminée (voir
filmatrix/services/run_rewards.py)."""

from datetime import date

from filmatrix.extensions import db
from filmatrix.models import Attempt, DailyChallenge, Question, User, UserBadge


def create_player(username: str = "Joueuse", email: str = "joueuse@filmatrix.fr", **extra) -> User:
    player = User(username=username, email=email, **extra)
    player.set_password("Azerty1!")
    db.session.add(player)
    db.session.commit()
    return player


def login(client, email: str) -> None:
    client.post("/connexion", data={"email": email, "password": "Azerty1!"})


def create_questions(app, count: int, mode: str = "qcm") -> list[int]:
    with app.app_context():
        ids = []
        for index in range(count):
            question = Question(
                mode=mode,
                prompt=f"Question {index}",
                payload={"options": ["A", "B"]},
                correct_answer={"index": 0},
                requires_account=False,
                difficulty="moyen",
            )
            db.session.add(question)
            db.session.commit()
            ids.append(question.id)
        return ids


def test_abandoning_a_run_keeps_nothing(client, app):
    """Répondre à des questions sans finir la partie ne doit rien créditer"""
    with app.app_context():
        player = create_player()
        player_id = player.id
    create_questions(app, 3)

    login(client, "joueuse@filmatrix.fr")
    client.get("/quiz/qcm/1")
    client.post("/quiz/qcm/1", data={"answer": "0"})
    client.post("/quiz/qcm/2", data={"answer": "0"})
    # La 3e question n'est jamais répondue : la partie est abandonnée.

    with app.app_context():
        refreshed = User.query.get(player_id)
        assert refreshed.total_xp == 0
        assert refreshed.coins == 0
        assert refreshed.total_correct_answers == 0
        assert Attempt.query.filter_by(user_id=player_id).count() == 0
        assert UserBadge.query.filter_by(user_id=player_id).count() == 0


def _seed_unreachable_daily_missions(player) -> None:
    """Neutralise les mini-missions du jour (cibles inatteignables) pour
    isoler les pièces gagnées pour les bonnes réponses elles-mêmes, sans
    qu'une mission complétée par hasard n'ajoute son propre bonus."""
    for slot, (challenge_type, extra) in enumerate(
        [("total_count", {}), ("mode_count", {"target_mode": "qcm"}), ("streak_count", {})]
    ):
        db.session.add(DailyChallenge(
            user_id=player.id, challenge_date=date.today(), slot=slot,
            challenge_type=challenge_type, target_value=1000, progress=0, **extra,
        ))
    db.session.commit()


def test_finishing_a_run_applies_everything(client, app):
    """Terminer la partie doit créditer XP, pièces, bonnes réponses et créer
    les Attempt correspondants"""
    with app.app_context():
        player = create_player()
        player_id = player.id
        _seed_unreachable_daily_missions(player)
    create_questions(app, 3)

    login(client, "joueuse@filmatrix.fr")
    client.get("/quiz/qcm/1")
    client.post("/quiz/qcm/1", data={"answer": "0"})
    client.post("/quiz/qcm/2", data={"answer": "0"})
    client.post("/quiz/qcm/3", data={"answer": "0"})

    with app.app_context():
        refreshed = User.query.get(player_id)
        assert refreshed.total_xp == 60  # 3 x 20 XP (difficulté moyen)
        assert refreshed.coins == 12  # 3 x 4 pièces
        assert refreshed.total_correct_answers == 3
        assert Attempt.query.filter_by(user_id=player_id).count() == 3

    with client.session_transaction() as sess:
        assert sess["run"]["finalized"] is True


def test_reloading_the_end_screen_does_not_double_award(client, app):
    """Recharger l'écran de fin ne doit pas recréditer une seconde fois"""
    with app.app_context():
        player = create_player()
        player_id = player.id
    create_questions(app, 1)

    login(client, "joueuse@filmatrix.fr")
    client.get("/quiz/qcm/1")
    client.post("/quiz/qcm/1", data={"answer": "0"})

    with app.app_context():
        xp_after_finish = User.query.get(player_id).total_xp

    # Rejoue le GET qui affiche termine.html (rechargement de la page).
    client.get("/quiz/qcm/2")

    with app.app_context():
        assert User.query.get(player_id).total_xp == xp_after_finish


def test_only_the_completed_run_contributes_to_mission_progress(client, app):
    """Deux parties le même jour, une seule terminée : seule celle-ci doit
    faire progresser une mini-mission - l'autre, abandonnée, ne compte pas"""
    with app.app_context():
        player = create_player()
        player_id = player.id
        # get_or_create_daily_missions attend toujours exactement 3 lignes
        # pour le jour : n'en créer qu'une déclencherait une tentative de
        # génération des 2 manquantes, en collision de slot avec celle-ci.
        mission = DailyChallenge(
            user_id=player.id, challenge_date=date.today(), slot=0,
            challenge_type="total_count", target_value=10, progress=0,
        )
        db.session.add(mission)
        db.session.add(DailyChallenge(
            user_id=player.id, challenge_date=date.today(), slot=1,
            challenge_type="mode_count", target_mode="qcm", target_value=10, progress=0,
        ))
        db.session.add(DailyChallenge(
            user_id=player.id, challenge_date=date.today(), slot=2,
            challenge_type="streak_count", target_value=10, progress=0,
        ))
        db.session.commit()
        mission_id = mission.id

    # Les questions de la partie B ne sont créées qu'après que la partie A
    # est bel et bien terminée : sinon le tirage de la partie A piocherait
    # aussi parmi les questions de B (même mode qcm), et sa 2e réponse ne
    # tomberait plus sur la dernière position de sa propre partie.
    login(client, "joueuse@filmatrix.fr")

    # Partie A : terminée jusqu'au bout.
    create_questions(app, 2)
    client.get("/quiz/qcm/1")
    client.post("/quiz/qcm/1", data={"answer": "0"})
    client.post("/quiz/qcm/2", data={"answer": "0"})

    with app.app_context():
        progress_after_run_a = DailyChallenge.query.get(mission_id).progress

    # Partie B : démarrée puis abandonnée après la 1re question seulement.
    create_questions(app, 2)
    client.get("/quiz/qcm/1")
    client.post("/quiz/qcm/1", data={"answer": "0"})

    with app.app_context():
        progress_after_abandoning_run_b = DailyChallenge.query.get(mission_id).progress

    assert progress_after_run_a == 2
    assert progress_after_abandoning_run_b == 2  # inchangé : run B jamais finalisée


def test_multiple_golden_ticket_thresholds_crossed_in_one_run(client, app, monkeypatch):
    """Une partie qui franchit plusieurs paliers de ticket d'or d'un coup doit
    créditer autant de tickets que de paliers franchis"""
    monkeypatch.setattr("filmatrix.services.run_rewards.CORRECT_ANSWERS_PER_TICKET", 2)

    with app.app_context():
        player = create_player(total_correct_answers=1, golden_tickets=0)
        player_id = player.id
    create_questions(app, 5)

    login(client, "joueuse@filmatrix.fr")
    client.get("/quiz/qcm/1")
    for position in range(1, 6):
        client.post(f"/quiz/qcm/{position}", data={"answer": "0"})

    with app.app_context():
        refreshed = User.query.get(player_id)
        # 1 (avant) + 5 bonnes réponses = 6 ; seuil à 2 -> paliers 2, 4, 6 = 3 tickets.
        assert refreshed.total_correct_answers == 6
        assert refreshed.golden_tickets == 3


def test_badge_only_awarded_once_the_run_is_finished(client, app):
    """Un badge basé sur le nombre total de réponses ne doit être attribué
    qu'à la fin de la partie qui en fait franchir le seuil, jamais avant"""
    with app.app_context():
        player = create_player()
        player_id = player.id
        # 99 réponses déjà en base : hundred_attempts se déclenche à 100.
        # Mode différent de la partie jouée plus bas (vrai_faux vs qcm) :
        # cette question d'historique ne doit pas se retrouver piochée dans
        # le tirage de la partie qcm, sous peine d'en fausser la taille.
        question_for_history = Question(
            mode="vrai_faux", prompt="Historique", payload={},
            correct_answer={"value": True}, difficulty="moyen",
        )
        db.session.add(question_for_history)
        db.session.commit()
        for _ in range(99):
            db.session.add(Attempt(user_id=player.id, question_id=question_for_history.id, is_correct=True))
        db.session.commit()

    create_questions(app, 2)
    login(client, "joueuse@filmatrix.fr")
    client.get("/quiz/qcm/1")
    client.post("/quiz/qcm/1", data={"answer": "0"})

    with app.app_context():
        # Après la 1re question de cette partie (pas encore la dernière) :
        # toujours pas de badge. L'Attempt de cette question elle-même n'est
        # pas encore créé (partie non finalisée) - seules les 99 réponses
        # historiques existent en base, sous le seuil de 100.
        assert UserBadge.query.filter_by(user_id=player_id, badge_code="hundred_attempts").count() == 0

    client.post("/quiz/qcm/2", data={"answer": "0"})

    with app.app_context():
        assert UserBadge.query.filter_by(user_id=player_id, badge_code="hundred_attempts").count() == 1
