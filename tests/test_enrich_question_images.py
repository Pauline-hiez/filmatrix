"""Tests du script d'enrichissement d'images de contexte (scripts/enrich_question_images.py).

Aucun appel réseau réel : search_movie/search_tv_show sont simulées.
"""

from scripts import enrich_question_images as enrich


def test_enrich_question_skips_spoiler_risk_modes():
    """enrich_question ne doit jamais toucher un mode où le titre est la
    réponse à deviner : c'est justement le rôle du second passage,
    enrich_admin_reference_image, sous une clé différente."""
    question = {
        "mode": "citation",
        "content_type": "film",
        "prompt": "De quel film vient cette réplique ?",
        "correct_answer": {"film": "Titanic"},
        "payload": {},
    }

    changed = enrich.enrich_question(question, titles=set(), local_images={}, cache={})

    assert changed is False
    assert "question_image_url" not in question["payload"]


def test_enrich_admin_reference_image_uses_the_answer_title(monkeypatch):
    """Contrairement à enrich_question, utiliser le titre de la réponse est
    ici sans risque : cette image n'est jamais montrée aux joueurs."""
    monkeypatch.setattr(enrich, "search_movie", lambda title: {"title": "Titanic", "poster_path": "/titanic.jpg"})

    question = {
        "mode": "citation",
        "content_type": "film",
        "prompt": "De quel film vient cette réplique ?",
        "correct_answer": {"film": "Titanic"},
        "payload": {},
    }

    changed = enrich.enrich_admin_reference_image(question, local_images={}, cache={})

    assert changed is True
    assert question["payload"]["admin_reference_image"] == "https://image.tmdb.org/t/p/w500/titanic.jpg"
    # Jamais sous la clé lue par le rendu joueur.
    assert "question_image_url" not in question["payload"]


def test_enrich_admin_reference_image_only_targets_modes_without_any_visual(monkeypatch):
    """casting/devinette_affiche ont déjà leur propre aperçu admin (photos
    d'acteurs, l'affiche elle-même) : pas besoin d'y ajouter un repère
    supplémentaire. emoji, lui, N'EN a pas assez (les indices seuls ne
    suffisent pas à reconnaître l'œuvre d'un coup d'œil) et fait donc
    désormais partie des modes couverts - voir
    test_enrich_admin_reference_image_targets_emoji_too ci-dessous."""
    monkeypatch.setattr(enrich, "search_movie", lambda title: {"title": "Titanic", "poster_path": "/titanic.jpg"})

    for mode in ("casting", "devinette_affiche", "qcm", "vrai_faux", "chronologie"):
        question = {
            "mode": mode,
            "content_type": "film",
            "prompt": "peu importe",
            "correct_answer": {"film": "Titanic"},
            "payload": {},
        }
        changed = enrich.enrich_admin_reference_image(question, local_images={}, cache={})
        assert changed is False, f"{mode} ne devrait pas recevoir de admin_reference_image"


def test_enrich_admin_reference_image_targets_emoji_too(monkeypatch):
    """Les emojis seuls (ex: 📱🖤🪞) n'identifient pas l'œuvre d'un coup d'œil
    dans la liste des questions admin, contrairement aux autres modes qui ont
    déjà une affiche ou une photo : emoji a donc besoin du même repère
    interne que citation/devinette/film_melange/blindtest."""
    monkeypatch.setattr(enrich, "search_movie", lambda title: {"title": "Titanic", "poster_path": "/titanic.jpg"})

    question = {
        "mode": "emoji",
        "content_type": "film",
        "prompt": "🚢🧊💔",
        "correct_answer": {"film": "Titanic"},
        "payload": {"visuals": [{"type": "openmoji", "value": "1F6A2"}]},
    }
    changed = enrich.enrich_admin_reference_image(question, local_images={}, cache={})
    assert changed is True
    assert question["payload"]["admin_reference_image"]


def test_enrich_admin_reference_image_does_not_overwrite_existing(monkeypatch):
    monkeypatch.setattr(
        enrich, "search_movie", lambda title: (_ for _ in ()).throw(AssertionError("ne devrait pas être appelé"))
    )

    question = {
        "mode": "devinette",
        "content_type": "film",
        "prompt": "peu importe",
        "correct_answer": {"film": "Titanic"},
        "payload": {"admin_reference_image": "https://images.example/deja-la.jpg"},
    }

    changed = enrich.enrich_admin_reference_image(question, local_images={}, cache={})

    assert changed is False
    assert question["payload"]["admin_reference_image"] == "https://images.example/deja-la.jpg"
