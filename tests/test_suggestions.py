"""Tests des suggestions de questions par les joueurs : quota, revue admin
(approbation telle quelle, modification avant approbation, refus) et
contrôle d'accès."""

import json
from datetime import datetime, timedelta

from filmatrix.extensions import db
from filmatrix.models import Question, QuestionSubmission, User
from filmatrix.services.suggestions import remaining_weekly_quota


def create_player(username: str = "Joueuse", email: str = "joueuse@filmatrix.fr") -> User:
    player = User(username=username, email=email)
    player.set_password("Azerty1!")
    db.session.add(player)
    db.session.commit()
    return player


def create_admin(username: str = "Admin", email: str = "admin@filmatrix.fr") -> User:
    admin = User(username=username, email=email, is_admin=True)
    admin.set_password("Azerty1!")
    db.session.add(admin)
    db.session.commit()
    return admin


def login(client, email: str) -> None:
    client.post("/connexion", data={"email": email, "password": "Azerty1!"})


def submission_payload(prompt: str = "Question de test", difficulty: str = "facile") -> dict:
    return {
        "mode": "qcm",
        "prompt": prompt,
        "content_type": "film",
        "difficulty": difficulty,
        "payload": json.dumps({"options": ["A", "B", "C", "D"]}),
        "correct_answer": json.dumps({"index": 0}),
    }


def submit(client, prompt: str = "Question de test") -> object:
    return client.post(
        "/suggestions/nouvelle",
        data=submission_payload(prompt),
        headers={"X-Requested-With": "XMLHttpRequest"},
    )


def create_submission(app, user, status: str = "pending", created_at=None, difficulty: str = "facile") -> int:
    """Crée une QuestionSubmission directement en base, sans passer par la route"""
    with app.app_context():
        submission = QuestionSubmission(
            user_id=user.id,
            mode="qcm",
            prompt="Question de test",
            payload={"options": ["A", "B", "C", "D"]},
            correct_answer={"index": 0},
            content_type="film",
            difficulty=difficulty,
            status=status,
        )
        if created_at is not None:
            submission.created_at = created_at
        db.session.add(submission)
        db.session.commit()
        return submission.id


def test_quota_allows_up_to_three_then_blocks_fourth(client, app):
    """Un joueur peut envoyer 3 suggestions, la 4e est refusée dans la même semaine"""
    with app.app_context():
        player_id = create_player().id
    login(client, "joueuse@filmatrix.fr")

    for index in range(3):
        response = submit(client, f"Question {index}")
        assert response.get_json()["success"] is True

    fourth = submit(client, "Question 4")
    assert fourth.status_code == 429
    assert fourth.get_json()["success"] is False

    with app.app_context():
        assert QuestionSubmission.query.filter_by(user_id=player_id).count() == 3


def test_rejected_submission_still_counts_against_quota(client, app):
    """Une suggestion refusée consomme quand même un slot du quota hebdomadaire"""
    with app.app_context():
        player = create_player()
        create_submission(app, player, status="pending")
        create_submission(app, player, status="pending")
        create_submission(app, player, status="rejected")

    login(client, "joueuse@filmatrix.fr")
    fourth = submit(client, "Question refusée en trop")

    assert fourth.status_code == 429
    with app.app_context():
        assert QuestionSubmission.query.filter_by(user_id=player.id).count() == 3


def test_quota_resets_after_seven_days(app):
    """Une suggestion vieille de plus de 7 jours ne compte plus dans le quota"""
    with app.app_context():
        player = create_player()
        create_submission(app, player, created_at=datetime.utcnow() - timedelta(days=8))

        assert remaining_weekly_quota(player) == 3


def test_approve_creates_playable_question_with_tags(client, app):
    """Approuver une suggestion telle quelle crée une Question jouable, avec ses tags"""
    with app.app_context():
        from filmatrix.models import Tag

        player = create_player()
        admin = create_admin()
        tag = Tag(name="Comédie", tag_type="genre")
        db.session.add(tag)
        db.session.commit()
        submission = QuestionSubmission(
            user_id=player.id,
            mode="qcm",
            prompt="Question taguée",
            payload={"options": ["A", "B", "C", "D"]},
            correct_answer={"index": 0},
            content_type="film",
            difficulty="difficile",
        )
        submission.tags = [tag]
        db.session.add(submission)
        db.session.commit()
        submission_id = submission.id
        tag_id = tag.id

    login(client, "admin@filmatrix.fr")
    response = client.post(f"/admin/suggestions/{submission_id}/approuver")
    assert response.status_code == 302

    with app.app_context():
        submission = QuestionSubmission.query.get(submission_id)
        assert submission.status == "approved"
        assert submission.question_id is not None

        question = Question.query.get(submission.question_id)
        assert question.prompt == "Question taguée"
        assert question.difficulty == "difficile"
        assert question.requires_account is False
        assert [tag.id for tag in question.tags] == [tag_id]


def test_approve_with_edits_preserves_original_and_marks_flag(client, app):
    """Approuver avec modifications ne réécrit jamais la soumission d'origine du joueur"""
    with app.app_context():
        player = create_player()
        admin = create_admin()
        submission = QuestionSubmission(
            user_id=player.id,
            mode="qcm",
            prompt="Version originale du joueur",
            payload={"options": ["A", "B", "C", "D"]},
            correct_answer={"index": 0},
            content_type="film",
            difficulty="facile",
        )
        db.session.add(submission)
        db.session.commit()
        submission_id = submission.id

    login(client, "admin@filmatrix.fr")
    response = client.post(
        f"/admin/suggestions/{submission_id}/modifier",
        data={
            "mode": "qcm",
            "prompt": "Version corrigée par l'admin",
            "content_type": "film",
            "difficulty": "difficile",
            "payload": json.dumps({"options": ["W", "X", "Y", "Z"]}),
            "correct_answer": json.dumps({"index": 1}),
        },
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert response.get_json()["success"] is True

    with app.app_context():
        submission = QuestionSubmission.query.get(submission_id)
        # La soumission d'origine du joueur n'est jamais réécrite.
        assert submission.prompt == "Version originale du joueur"
        assert submission.difficulty == "facile"
        # Les retouches admin vivent dans les colonnes reviewed_*.
        assert submission.reviewed_prompt == "Version corrigée par l'admin"
        assert submission.reviewed_difficulty == "difficile"
        assert submission.was_edited_by_admin is True
        assert submission.status == "approved"

        question = Question.query.get(submission.question_id)
        assert question.prompt == "Version corrigée par l'admin"
        assert question.difficulty == "difficile"


def test_reject_requires_reason(client, app):
    """Un refus sans motif ne change rien ; avec motif, la suggestion est marquée refusée"""
    with app.app_context():
        player = create_player()
        admin = create_admin()
        submission_id = create_submission(app, player, status="pending")

    login(client, "admin@filmatrix.fr")

    without_reason = client.post(f"/admin/suggestions/{submission_id}/rejeter", data={})
    assert without_reason.status_code == 302
    with app.app_context():
        submission = QuestionSubmission.query.get(submission_id)
        assert submission.status == "pending"

    with_reason = client.post(
        f"/admin/suggestions/{submission_id}/rejeter",
        data={"reason": "Doublon d'une question existante"},
    )
    assert with_reason.status_code == 302
    with app.app_context():
        submission = QuestionSubmission.query.get(submission_id)
        assert submission.status == "rejected"
        assert submission.rejection_reason == "Doublon d'une question existante"
        assert submission.question_id is None


def test_non_admin_cannot_access_admin_suggestion_routes(client, app):
    """Un joueur non-admin ne doit jamais accéder aux routes de revue admin"""
    with app.app_context():
        player = create_player()
        submission_id = create_submission(app, player, status="pending")

    login(client, "joueuse@filmatrix.fr")

    assert client.get("/admin/suggestions").status_code == 403
    assert client.post(f"/admin/suggestions/{submission_id}/approuver").status_code == 403
    assert client.get(f"/admin/suggestions/{submission_id}/modifier").status_code == 403
    assert client.post(f"/admin/suggestions/{submission_id}/rejeter", data={"reason": "x"}).status_code == 403


def test_deleting_question_nulls_submission_link(client, app):
    """Supprimer la question créée par une suggestion approuvée garde l'historique, sans lien mort"""
    with app.app_context():
        player = create_player()
        admin = create_admin()
        submission_id = create_submission(app, player, status="pending")

    login(client, "admin@filmatrix.fr")
    client.post(f"/admin/suggestions/{submission_id}/approuver")

    with app.app_context():
        submission = QuestionSubmission.query.get(submission_id)
        question_id = submission.question_id
        assert question_id is not None

    client.post(f"/admin/questions/{question_id}/supprimer")

    with app.app_context():
        submission = QuestionSubmission.query.get(submission_id)
        assert submission.question_id is None
        assert submission.status == "approved"
