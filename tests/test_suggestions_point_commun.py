"""Tests du mode Point commun dans le circuit de suggestion joueur : un
joueur propose (filmatrix/routes/suggestions.py), un admin approuve
(filmatrix/routes/admin.py) - resolve_point_commun_works est partagée entre
les deux circuits (filmatrix/services/works.py)."""

import json
from types import SimpleNamespace
from unittest.mock import patch

from filmatrix.extensions import db
from filmatrix.models import Question, QuestionSubmission, User

PATCH_TARGET = "filmatrix.services.works.get_or_create_work"


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


def fake_work(tmdb_id: int, content_type: str = "film"):
    return SimpleNamespace(
        id=tmdb_id,
        tmdb_id=tmdb_id,
        content_type=content_type,
        title=f"Œuvre {tmdb_id}",
        poster_url=f"https://example.com/{tmdb_id}.jpg",
    )


def point_commun_form_data(work_tmdb_ids=(201, 202, 203)) -> dict:
    data = {
        "mode": "point_commun",
        "prompt": "Quel est le point commun entre ces trois œuvres ?",
        "content_type": "film",
        "difficulty": "moyen",
        "payload": json.dumps({"options": ["Leurre A", "Leurre B", "Bonne réponse", "Leurre C"]}),
        "correct_answer": json.dumps({"index": 2}),
    }
    for i, tmdb_id in enumerate(work_tmdb_ids, start=1):
        data[f"work_tmdb_id_{i}"] = str(tmdb_id)
        data[f"work_content_type_{i}"] = "film"
    return data


def test_a_player_can_submit_a_point_commun_suggestion(client, app):
    """La soumission d'un joueur doit résoudre les 3 œuvres exactement comme
    le formulaire admin (même fonction partagée)."""
    with app.app_context():
        create_player()
    login(client, "joueuse@filmatrix.fr")

    with patch(PATCH_TARGET, side_effect=lambda tmdb_id, content_type: fake_work(tmdb_id, content_type)) as mock_get_or_create:
        response = client.post(
            "/suggestions/nouvelle", data=point_commun_form_data(), follow_redirects=True
        )

    assert response.status_code == 200
    assert mock_get_or_create.call_count == 3

    with app.app_context():
        submission = QuestionSubmission.query.filter_by(mode="point_commun").first()
        assert submission is not None
        works = submission.payload["works"]
        assert [w["tmdb_id"] for w in works] == [201, 202, 203]
        assert submission.status == "pending"


def test_a_player_submission_fails_cleanly_without_all_three_works(client, app):
    """Même garde que le formulaire admin : pas de suggestion à moitié faite."""
    with app.app_context():
        create_player()
    login(client, "joueuse@filmatrix.fr")

    incomplete_data = point_commun_form_data()
    del incomplete_data["work_tmdb_id_2"]

    with patch(PATCH_TARGET, side_effect=lambda tmdb_id, content_type: fake_work(tmdb_id, content_type)):
        response = client.post("/suggestions/nouvelle", data=incomplete_data)

    assert response.status_code == 400

    with app.app_context():
        assert QuestionSubmission.query.filter_by(mode="point_commun").count() == 0


def test_admin_can_approve_a_point_commun_suggestion_as_is(client, app):
    """L'approbation telle quelle (sans modification) doit créer une
    Question jouable avec le même payload.works que la suggestion."""
    with app.app_context():
        player = create_player()
        create_admin()
        submission = QuestionSubmission(
            user_id=player.id,
            mode="point_commun",
            prompt="Quel est le point commun entre ces trois œuvres ?",
            payload={
                "works": [
                    {"work_id": 1, "tmdb_id": 201, "content_type": "film", "title": "Œuvre 201", "poster_url": "https://example.com/201.jpg"},
                    {"work_id": 2, "tmdb_id": 202, "content_type": "film", "title": "Œuvre 202", "poster_url": "https://example.com/202.jpg"},
                    {"work_id": 3, "tmdb_id": 203, "content_type": "film", "title": "Œuvre 203", "poster_url": "https://example.com/203.jpg"},
                ],
                "options": ["Leurre A", "Leurre B", "Bonne réponse", "Leurre C"],
            },
            correct_answer={"index": 2},
            content_type="film",
            difficulty="moyen",
        )
        db.session.add(submission)
        db.session.commit()
        submission_id = submission.id

    login(client, "admin@filmatrix.fr")
    response = client.post(f"/admin/suggestions/{submission_id}/approuver", follow_redirects=True)

    assert response.status_code == 200

    with app.app_context():
        question = Question.query.filter_by(mode="point_commun").first()
        assert question is not None
        assert len(question.payload["works"]) == 3
        assert question.correct_answer == {"index": 2}
