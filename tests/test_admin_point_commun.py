"""Tests du support admin du mode Point commun (création/édition d'une
question via le formulaire générique, filmatrix/routes/admin.py).

get_or_create_work est mockée (comme tests/test_works.py le fait pour les
fonctions TMDB sous-jacentes) : ces tests portent sur le câblage du
formulaire, pas sur l'intégration TMDB réelle."""

import json
from types import SimpleNamespace
from unittest.mock import patch

from filmatrix.extensions import db
from filmatrix.models import Question, User

PATCH_TARGET = "filmatrix.services.works.get_or_create_work"


def create_admin(username: str = "AdminPointCommun") -> User:
    admin = User(username=username, email=f"{username.lower()}@filmatrix.fr", is_admin=True)
    admin.set_password("Azerty1!")
    db.session.add(admin)
    db.session.commit()
    return admin


def login_admin(client, email: str) -> None:
    client.post("/connexion", data={"email": email, "password": "Azerty1!"})


def fake_work(tmdb_id: int, content_type: str = "film"):
    """Reproduit ce que get_or_create_work renverrait, sans toucher Work/TMDB."""
    return SimpleNamespace(
        id=tmdb_id,  # ré-utilise tmdb_id comme id factice, pas de vraie ligne Work nécessaire ici
        tmdb_id=tmdb_id,
        content_type=content_type,
        title=f"Œuvre {tmdb_id}",
        poster_url=f"https://example.com/{tmdb_id}.jpg",
    )


def point_commun_form_data(work_tmdb_ids=(101, 102, 103)) -> dict:
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


def test_creating_a_point_commun_question_resolves_its_three_works(client, app):
    """La création doit appeler get_or_create_work pour chacune des 3 œuvres
    et stocker le résultat (work_id/tmdb_id/content_type/title/poster_url)
    dans payload.works, sans jamais le construire côté client."""
    with app.app_context():
        create_admin()
    login_admin(client, "adminpointcommun@filmatrix.fr")

    with patch(PATCH_TARGET, side_effect=lambda tmdb_id, content_type: fake_work(tmdb_id, content_type)) as mock_get_or_create:
        response = client.post(
            "/admin/questions/nouvelle", data=point_commun_form_data(), follow_redirects=True
        )

    assert response.status_code == 200
    assert mock_get_or_create.call_count == 3

    with app.app_context():
        question = Question.query.filter_by(mode="point_commun").first()
        assert question is not None
        works = question.payload["works"]
        assert len(works) == 3
        assert [w["tmdb_id"] for w in works] == [101, 102, 103]
        assert all({"work_id", "tmdb_id", "content_type", "title", "poster_url"} <= w.keys() for w in works)
        assert question.correct_answer == {"index": 2}


def test_creating_a_point_commun_question_fails_cleanly_without_all_three_works(client, app):
    """Un formulaire incomplet (une des 3 œuvres manquante) ne doit jamais
    créer de question à moitié faite - juste un message d'erreur."""
    with app.app_context():
        create_admin()
    login_admin(client, "adminpointcommun@filmatrix.fr")

    incomplete_data = point_commun_form_data()
    del incomplete_data["work_tmdb_id_3"]

    with patch(PATCH_TARGET, side_effect=lambda tmdb_id, content_type: fake_work(tmdb_id, content_type)):
        response = client.post("/admin/questions/nouvelle", data=incomplete_data, follow_redirects=True)

    assert response.status_code == 200
    assert "Sélectionne les 3 œuvres du mode Point commun.".encode() in response.data

    with app.app_context():
        assert Question.query.filter_by(mode="point_commun").count() == 0


def test_editing_a_point_commun_question_can_replace_a_single_work(client, app):
    """Changer une seule des 3 œuvres en édition doit mettre à jour
    uniquement cette entrée, les deux autres restant intactes."""
    with app.app_context():
        create_admin()
        question = Question(
            mode="point_commun",
            prompt="Quel est le point commun entre ces trois œuvres ?",
            content_type="film",
            difficulty="moyen",
            payload={
                "works": [
                    {"work_id": 1, "tmdb_id": 101, "content_type": "film", "title": "Œuvre 101", "poster_url": "https://example.com/101.jpg"},
                    {"work_id": 2, "tmdb_id": 102, "content_type": "film", "title": "Œuvre 102", "poster_url": "https://example.com/102.jpg"},
                    {"work_id": 3, "tmdb_id": 103, "content_type": "film", "title": "Œuvre 103", "poster_url": "https://example.com/103.jpg"},
                ],
                "options": ["Leurre A", "Leurre B", "Bonne réponse", "Leurre C"],
            },
            correct_answer={"index": 2},
        )
        db.session.add(question)
        db.session.commit()
        question_id = question.id

    login_admin(client, "adminpointcommun@filmatrix.fr")

    # Seule la 2e œuvre change (999 au lieu de 102).
    updated_data = point_commun_form_data(work_tmdb_ids=(101, 999, 103))

    with patch(PATCH_TARGET, side_effect=lambda tmdb_id, content_type: fake_work(tmdb_id, content_type)):
        response = client.post(
            f"/admin/questions/{question_id}/modifier", data=updated_data, follow_redirects=True
        )

    assert response.status_code == 200

    with app.app_context():
        question = Question.query.get(question_id)
        tmdb_ids = [w["tmdb_id"] for w in question.payload["works"]]
        assert tmdb_ids == [101, 999, 103]
