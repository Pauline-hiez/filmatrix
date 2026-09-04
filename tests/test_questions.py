"""Tests de la résolution des propositions et images de QCM."""

from filmatrix.extensions import db
from filmatrix.models import Character, Question, Tag
from filmatrix.services.questions import question_image_url, shuffle_options


def create_tag(name: str = "Friends") -> Tag:
    tag = Tag(name=name, tag_type="univers")
    db.session.add(tag)
    db.session.commit()
    return tag


def create_character(tag: Tag, name: str, image_url: str | None) -> Character:
    character = Character(name=name, tag_id=tag.id, rarity="commun", image_url=image_url)
    db.session.add(character)
    db.session.commit()
    return character


def create_qcm(options: list[str]) -> Question:
    question = Question(
        mode="qcm",
        prompt="Dans Friends, quel membre du groupe est paléontologue ?",
        payload={"options": options},
        correct_answer={"index": 1},
    )
    db.session.add(question)
    db.session.commit()
    return question


def test_partial_matches_are_not_shown_at_all(app):
    """Si une seule proposition sur quatre a une image, aucune ne doit s'afficher
    (mélange bancal texte/image plutôt qu'un rendu cohérent, cf. capture utilisateur)."""
    with app.app_context():
        tag = create_tag()
        # Seul Chandler a un portrait dans la collection : cas réel qui
        # produisait le rendu bancal (une seule image sur quatre options).
        create_character(tag, "Chandler Bing", image_url="chandler.jpg")
        question = create_qcm(["Mike Hannigan", "Chandler Bing", "Joey Tribbiani", "Ross Geller"])

        options = shuffle_options(question)

        assert len(options) == 4
        assert all(image_url is None for _, _, image_url in options)


def test_full_matches_are_all_shown(app):
    """Si les quatre propositions ont une image, elles doivent toutes s'afficher."""
    with app.app_context():
        tag = create_tag()
        names = ["Mike Hannigan", "Chandler Bing", "Joey Tribbiani", "Ross Geller"]
        for name in names:
            create_character(tag, name, image_url=f"{name}.jpg")
        question = create_qcm(names)

        options = shuffle_options(question)

        assert len(options) == 4
        assert all(image_url is not None for _, _, image_url in options)


def test_no_matches_stays_text_only(app):
    """Si aucune proposition n'a d'image, la question reste simplement en texte."""
    with app.app_context():
        question = create_qcm(["Un", "Deux", "Trois", "Quatre"])

        options = shuffle_options(question)

        assert len(options) == 4
        assert all(image_url is None for _, _, image_url in options)


def test_explicit_option_images_win_when_complete(app):
    """Des option_images explicites dans le payload (enrichissement TMDB)
    priment et s'affichent toutes si elles couvrent bien les quatre options."""
    with app.app_context():
        question = create_qcm(["Un", "Deux", "Trois", "Quatre"])
        # Réassignation complète (et non mutation en place) : une colonne JSON
        # ne détecte pas une modification interne au dict, seule une nouvelle
        # valeur affectée à l'attribut est suivie par SQLAlchemy.
        question.payload = {**question.payload, "option_images": ["a.jpg", "b.jpg", "c.jpg", "d.jpg"]}
        db.session.commit()

        options = shuffle_options(question)

        assert all(image_url is not None for _, _, image_url in options)


def test_question_image_url_uses_icon_for_citation(app):
    """Citation demande de deviner l'œuvre : jamais son affiche, seulement
    l'icône générique du mode (mode_image_icon)."""
    with app.test_request_context():
        question = Question(
            mode="citation",
            prompt="«I'll be back.» De quel film vient cette réplique ?",
            payload={},
            correct_answer={"film": "Terminator"},
        )
        db.session.add(question)
        db.session.commit()

        url = question_image_url(question)

        assert url is not None
        assert url.endswith("/images/icones/citation.png")


def test_question_image_url_never_leaks_answer_poster_for_spoiler_modes(app):
    """Filet de sécurité : même si le payload contenait déjà l'affiche de la
    réponse (ancienne donnée corrompue par un enrichissement trop permissif),
    un mode où le titre est la réponse à deviner ne doit jamais la révéler."""
    with app.test_request_context():
        question = Question(
            mode="devinette",
            prompt="Quel film se cache derrière ces indices ?",
            payload={
                "question_image_url": "https://images.example/titanic-answer.jpg",
                "hints": ["Un indice"],
            },
            correct_answer={"film": "Titanic"},
        )
        db.session.add(question)
        db.session.commit()

        url = question_image_url(question)

        assert url != "https://images.example/titanic-answer.jpg"
        assert url is not None and url.endswith("/images/icones/devinette.png")


def test_question_image_url_none_for_modes_with_their_own_visual(app):
    """Casting, devinette_affiche et emoji ont déjà leur propre image comme
    mécanique de jeu : pas de doublon d'illustration."""
    with app.test_request_context():
        for mode in ("casting", "devinette_affiche", "emoji"):
            question = Question(
                mode=mode,
                prompt="Prompt",
                payload={},
                correct_answer={"film": "Un film"},
            )
            db.session.add(question)
            db.session.commit()

            assert question_image_url(question) is None


def test_question_image_url_none_for_mode_without_icon_yet(app):
    """Un mode sans icône dédiée pour l'instant (ex. film_melange) reste
    simplement sans image, plutôt que planter ou en emprunter une par erreur."""
    with app.test_request_context():
        question = Question(
            mode="film_melange",
            prompt="",
            payload={},
            correct_answer={"title": "Avatar"},
        )
        db.session.add(question)
        db.session.commit()

        assert question_image_url(question) is None


def test_question_image_url_shows_real_poster_for_vrai_faux(app):
    """vrai_faux nomme toujours le titre dans l'énoncé : son affiche réelle
    peut illustrer la question sans rien révéler de plus."""
    with app.test_request_context():
        poster_question = Question(
            mode="devinette_affiche",
            content_type="film",
            prompt="",
            payload={"poster_url": "https://images.example/titanic.jpg"},
            correct_answer={"film": "Titanic"},
        )
        vrai_faux_question = Question(
            mode="vrai_faux",
            content_type="film",
            prompt="Le film Titanic est sorti en 1997.",
            payload={},
            correct_answer={"value": True},
        )
        db.session.add_all([poster_question, vrai_faux_question])
        db.session.commit()

        assert question_image_url(vrai_faux_question) == "https://images.example/titanic.jpg"
