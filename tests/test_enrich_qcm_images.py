"""Tests du script d'enrichissement d'images QCM (scripts/enrich_qcm_images.py).

Aucun appel réseau réel : les fonctions TMDB utilisées par le script sont
simulées, pour valider la logique de correspondance sans dépendre de l'API.
"""

from scripts import enrich_qcm_images as enrich


def test_question_kind_detects_character_questions():
    """Une question 'membre du groupe' doit être classée comme personnage."""
    assert enrich.question_kind("Dans Friends, quel membre du groupe est paléontologue ?") == "character"
    assert enrich.question_kind("Qui interprète le clown dans Ça ?") == "person"
    assert enrich.question_kind("Dans quel film apparaît Ghostface ?") == "work"
    assert enrich.question_kind("Combien de saisons compte cette série ?") is None


def test_extract_work_title_from_prompt():
    assert enrich.extract_work_title("Dans Friends, quel membre du groupe est paléontologue ?") == "Friends"
    assert enrich.extract_work_title("Dans la série The Office, qui est le manager ?") == "The Office"
    assert enrich.extract_work_title("Quel est le budget de ce film ?") is None


def test_image_for_character_matches_normalized_character_field(monkeypatch):
    """Le portrait doit venir du casting de la bonne œuvre, avec correspondance
    normalisée sur le champ 'character' (qui contient parfois des variantes)."""
    monkeypatch.setattr(enrich, "search_tv_show", lambda title: {"id": 1668})
    monkeypatch.setattr(
        enrich,
        "get_tv_show_cast",
        lambda show_id, limit=25: [
            {"name": "Matthew Perry", "character": "Chandler Muriel Bing", "profile_path": "/chandler.jpg"},
            {"name": "David Schwimmer", "character": "Dr. Ross Geller", "profile_path": "/ross.jpg"},
        ],
    )

    cache: dict = {}
    image_url = enrich.image_for_character("Friends", "serie", "Chandler Bing", cache)

    assert image_url == "https://image.tmdb.org/t/p/w500/chandler.jpg"
    # Le casting ne doit être recherché qu'une fois par œuvre, pas par personnage.
    assert ("cast", "serie", "friends") in cache


def test_image_for_character_returns_none_without_match(monkeypatch):
    monkeypatch.setattr(enrich, "search_tv_show", lambda title: {"id": 1668})
    monkeypatch.setattr(enrich, "get_tv_show_cast", lambda show_id, limit=25: [])

    assert enrich.image_for_character("Friends", "serie", "Chandler Bing", {}) is None


def test_enrich_question_fills_character_options(monkeypatch):
    monkeypatch.setattr(enrich, "search_tv_show", lambda title: {"id": 1668})
    monkeypatch.setattr(
        enrich,
        "get_tv_show_cast",
        lambda show_id, limit=25: [
            {"name": "Matthew Perry", "character": "Chandler Bing", "profile_path": "/chandler.jpg"},
        ],
    )

    question = {
        "mode": "qcm",
        "content_type": "serie",
        "prompt": "Dans Friends, quel membre du groupe est paléontologue ?",
        "payload": {"options": ["Mike Hannigan", "Chandler Bing", "Joey Tribbiani", "Ross Geller"]},
    }

    changed, added, _ = enrich.enrich_question(question, {})

    assert changed is True
    assert added == 1
    assert question["payload"]["option_images"][1] == "https://image.tmdb.org/t/p/w500/chandler.jpg"
    assert question["payload"]["option_images"][0] is None


def test_enrich_question_never_assigns_the_same_image_twice(monkeypatch):
    """Deux personnages doublés par le même acteur (ex. animation) ne doivent
    pas recevoir la même photo : mieux vaut rester en texte pour l'un des deux
    que de faire deviner la réponse par élimination visuelle."""
    monkeypatch.setattr(enrich, "search_tv_show", lambda title: {"id": 1})
    monkeypatch.setattr(
        enrich,
        "get_tv_show_cast",
        lambda show_id, limit=25: [
            {"name": "Trey Parker", "character": "Stan Marsh / Cartman", "profile_path": "/trey.jpg"},
            {"name": "Matt Stone", "character": "Kyle Broflovski / Kenny McCormick", "profile_path": "/matt.jpg"},
        ],
    )

    question = {
        "mode": "qcm",
        "content_type": "serie",
        "prompt": "Dans South Park, quel personnage meurt dans presque chaque épisode ?",
        "payload": {"options": ["Kenny", "Cartman", "Kyle", "Stan"]},
    }

    changed, added, _ = enrich.enrich_question(question, {})

    images = question["payload"]["option_images"]
    non_null = [image for image in images if image]
    assert changed is True
    # Un seul des deux personnages partageant chaque acteur garde son image.
    assert len(non_null) == len(set(non_null))
    assert added == len(non_null)


def test_enrich_question_skips_character_without_extractable_work(monkeypatch):
    """Sans titre d'œuvre identifiable en tête de phrase, on ne devine jamais."""
    question = {
        "mode": "qcm",
        "content_type": "serie",
        "prompt": "Quel personnage est paléontologue ?",
        "payload": {"options": ["Mike Hannigan", "Chandler Bing", "Joey Tribbiani", "Ross Geller"]},
    }

    changed, added, _ = enrich.enrich_question(question, {})

    assert changed is False
    assert added == 0
    assert "option_images" not in question["payload"]
