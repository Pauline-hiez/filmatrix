"""Tests des niveaux de jeu : temps de réponse accordé et récompenses."""

from filmatrix.extensions import db
from filmatrix.services.levels import coins_for_level, duration_for, resolve_level, xp_for_level
from filmatrix.models import Question, User


def test_higher_level_leaves_less_time():
    """Plus le niveau monte, moins le joueur a de temps pour répondre"""
    assert duration_for("facile", "qcm") == 22
    assert duration_for("moyen", "qcm") == 16
    assert duration_for("difficile", "qcm") == 12


def test_higher_level_pays_more():
    """Plus le niveau monte, plus une bonne réponse rapporte"""
    assert (xp_for_level("facile"), coins_for_level("facile")) == (10, 2)
    assert (xp_for_level("moyen"), coins_for_level("moyen")) == (20, 4)
    assert (xp_for_level("difficile"), coins_for_level("difficile")) == (30, 6)


def test_blindtest_keeps_its_own_duration():
    """Le blindtest garde 30 secondes quel que soit le niveau choisi"""
    for level in ["facile", "moyen", "difficile"]:
        assert duration_for(level, "blindtest") == 30


def test_unknown_level_falls_back_on_default():
    """Un niveau absent ou fantaisiste dans l'URL ne doit pas faire planter la partie"""
    assert resolve_level(None) == "moyen"
    assert resolve_level("legendaire") == "moyen"
    assert duration_for("legendaire", "qcm") == 16
    assert xp_for_level(None) == 20


def create_question(app, mode="qcm"):
    """Crée une question simple dans la base de test"""
    with app.app_context():
        db.session.add(
            Question(
                mode=mode,
                prompt="Question de test niveau",
                payload={"options": ["A", "B"]},
                correct_answer={"index": 0},
                requires_account=False,
            )
        )
        db.session.commit()


def test_timer_sent_to_the_page_follows_the_chosen_level(client, app):
    """La barre de temps doit porter la durée du niveau demandé dans l'URL"""
    create_question(app)

    assert b'data-duration="22"' in client.get("/quiz/qcm/1?level=facile").data
    assert b'data-duration="12"' in client.get("/quiz/qcm/1?level=difficile").data
    # Sans niveau dans l'URL, on retombe sur le niveau par défaut.
    assert b'data-duration="16"' in client.get("/quiz/qcm/1").data


def test_reward_follows_the_chosen_level_not_the_question(client, app):
    """Une même question doit rapporter davantage en difficile qu'en facile"""
    create_question(app)

    with app.app_context():
        player = User(username="Joueuse", email="joueuse@filmatrix.fr")
        player.set_password("Azerty1!")
        db.session.add(player)
        db.session.commit()

    client.post("/connexion", data={"email": "joueuse@filmatrix.fr", "password": "Azerty1!"})
    client.post("/quiz/qcm/1?level=difficile", data={"answer": "0"})

    with app.app_context():
        player = User.query.filter_by(username="Joueuse").first()
        # La question est enregistrée en "facile", elle ne décide plus de rien.
        assert player.total_xp == 30
        assert player.coins == 6


def create_tagged_question(app, mode, tag_name, count=None):
    """Crée des questions rattachées à un thème, dans le mode demandé

    Un thème n'est proposé sur l'écran de préparation qu'à partir d'un
    certain nombre de questions (cf. TAG_MIN_QUESTIONS dans
    services/questions.py) : count s'aligne par défaut sur ce seuil, pour
    qu'un thème testé ici apparaisse bien tel qu'un joueur le verrait."""
    from filmatrix.models import Tag
    from filmatrix.services.questions import DEFAULT_TAG_MIN_QUESTIONS

    if count is None:
        count = DEFAULT_TAG_MIN_QUESTIONS

    with app.app_context():
        tag = Tag.query.filter_by(name=tag_name).first()
        if tag is None:
            tag = Tag(name=tag_name, tag_type="saga")
            db.session.add(tag)

        for index in range(count):
            question = Question(
                mode=mode,
                prompt=f"Question de test thème {index}",
                payload={"options": ["A", "B"]},
                correct_answer={"index": 0},
            )
            question.tags.append(tag)
            db.session.add(question)
        db.session.commit()


def test_setup_screen_only_offers_tags_present_in_the_mode(client, app):
    """Un thème sans question dans le mode choisi ne doit pas être proposé"""
    create_tagged_question(app, mode="qcm", tag_name="Star Wars")
    create_tagged_question(app, mode="citation", tag_name="Le Parrain")

    page_qcm = client.get("/quiz/qcm").data

    assert "Star Wars".encode() in page_qcm
    assert "Le Parrain".encode() not in page_qcm

    page_citation = client.get("/quiz/citation").data

    assert "Le Parrain".encode() in page_citation
    assert "Star Wars".encode() not in page_citation


def test_setup_screen_lists_no_tag_for_a_mode_without_tagged_questions(client, app):
    """Un mode dont aucune question n'est taguée ne doit proposer que « Tous les thèmes »"""
    create_tagged_question(app, mode="qcm", tag_name="Star Wars")

    page_emoji = client.get("/quiz/emoji").data

    assert "Tous les genres".encode() in page_emoji
    assert "Tous les univers".encode() in page_emoji
    assert "Tous les pays".encode() in page_emoji
    assert "Toutes les époques".encode() in page_emoji
    assert "Star Wars".encode() not in page_emoji
