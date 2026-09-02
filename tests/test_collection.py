"""Tests de la logique métier de collection de personnages (fragments, déblocage)."""

from filmatrix.extensions import db
from filmatrix.models import Character, Tag, User, Question
from filmatrix.services.collection import (
    add_fragments,
    award_fragment_for_question,
    fragment_result_payload,
    get_characters_for_tag,
    get_or_create_progress,
)




def create_test_user(username: str = "Collectionneur") -> User:
    """Crée un utilisateur de test en base"""
    user = User(username=username, email=f"{username.lower()}@filmatrix.fr")
    user.set_password("Azerty1!")
    db.session.add(user)
    db.session.commit()
    return user


def create_test_tag(name: str = "Harry Potter", tag_type: str = "saga") -> Tag:
    """Crée un tag de franchise de test en base (saga ou univers)"""
    tag = Tag(name=name, tag_type=tag_type)
    db.session.add(tag)
    db.session.commit()
    return tag


def create_test_character(tag: Tag, name: str = "Harry Potter", fragments_required: int = 5) -> Character:
    """Crée un personnage de test en base"""
    character = Character(
        name=name,
        tag_id=tag.id,
        rarity="legendaire",
        fragments_required=fragments_required,
    )
    db.session.add(character)
    db.session.commit()
    return character


def test_add_fragments_creates_progress_if_missing(app):
    """L'ajout de fragments doit créer un enregistrement de progression s'il n'en existe pas encore"""
    with app.app_context():
        user = create_test_user()
        tag = create_test_tag()
        character = create_test_character(tag)

        add_fragments(user, character, 2)
        db.session.commit()

        progress = get_or_create_progress(user, character)
        assert progress.fragments == 2


def test_add_fragments_unlocks_character_at_threshold(app):
    """L'obtention du nombre de fragments requis doit débloquer le personnage"""
    with app.app_context():
        user = create_test_user()
        tag = create_test_tag()
        character = create_test_character(tag, fragments_required=3)

        add_fragments(user, character, 2)
        db.session.commit()
        just_unlocked = add_fragments(user, character, 1)
        db.session.commit()

        assert just_unlocked is True
        progress = get_or_create_progress(user, character)
        assert progress.unlocked_at is not None


def test_add_fragments_does_not_unlock_twice(app):
    """Une fois déverrouillé, l'ajout de fragments supplémentaires ne doit pas déclencher un nouveau déverrouillage"""
    with app.app_context():
        user = create_test_user()
        tag = create_test_tag()
        character = create_test_character(tag, fragments_required=2)

        add_fragments(user, character, 2)
        db.session.commit()
        just_unlocked_again = add_fragments(user, character, 1)
        db.session.commit()

        assert just_unlocked_again is False


def test_add_fragments_caps_at_required_amount(app):
    """Les fragments ne doivent jamais dépasser le seuil requis"""
    with app.app_context():
        user = create_test_user()
        tag = create_test_tag()
        character = create_test_character(tag, fragments_required=3)

        add_fragments(user, character, 10)
        db.session.commit()

        progress = get_or_create_progress(user, character)
        assert progress.fragments == 3


def test_get_characters_for_tag_shows_all_with_progress(app):
    """Doit renvoyer tous les personnages en fonction de la progression du joueur"""
    with app.app_context():
        user = create_test_user()
        tag = create_test_tag()
        character_unlocked = create_test_character(tag, name="Harry Potter", fragments_required=2)
        character_locked = create_test_character(tag, name="Voldemort", fragments_required=5)

        add_fragments(user, character_unlocked, 2)
        db.session.commit()

        characters = get_characters_for_tag(user, tag.id)
        names_and_status = {c["name"]: c["is_unlocked"] for c in characters}

        assert names_and_status["Harry Potter"] is True
        assert names_and_status["Voldemort"] is False

def create_test_question(tags: list[Tag] | None = None) -> Question:
    """Crée une question de test, éventuellement liée à des tags."""
    question = Question(
        mode="citation",
        prompt="Question de test",
        payload={},
        correct_answer={"film": "Test"},
        requires_account=False,
    )
    if tags:
        question.tags = tags
    db.session.add(question)
    db.session.commit()
    return question


def test_award_fragment_returns_none_without_franchise_tag(app):
    """Une question sans tag de franchise (ni saga ni univers) ne doit rien donner."""
    with app.app_context():
        user = create_test_user()
        question = create_test_question()

        result = award_fragment_for_question(user, question)

        assert result is None


def test_award_fragment_returns_none_without_characters(app):
    """Un tag de franchise sans personnage ne doit rien donner."""
    with app.app_context():
        user = create_test_user()
        tag = create_test_tag()
        question = create_test_question(tags=[tag])

        result = award_fragment_for_question(user, question)

        assert result is None


def test_award_fragment_gives_fragment_to_locked_character(app):
    """A correct answer should give one fragment to a locked character of the saga."""
    with app.app_context():
        user = create_test_user()
        tag = create_test_tag()
        character = create_test_character(tag, fragments_required=5)
        question = create_test_question(tags=[tag])

        result = award_fragment_for_question(user, question)
        db.session.commit()

        assert result is not None
        chosen_character, just_unlocked = result
        assert chosen_character.id == character.id
        assert just_unlocked is False

        progress = get_or_create_progress(user, character)
        assert progress.fragments == 1


def test_award_fragment_ignores_already_unlocked_characters(app):
    """Un personnage déjà débloqué ne doit pas recevoir de fragment supplémentaire."""
    with app.app_context():
        user = create_test_user()
        tag = create_test_tag()
        character = create_test_character(tag, fragments_required=1)
        question = create_test_question(tags=[tag])

        award_fragment_for_question(user, question)
        db.session.commit()

        result = award_fragment_for_question(user, question)

        assert result is None


def test_award_fragment_targets_univers_tag(app):
    """Une question liée à un tag « univers » doit aussi donner un fragment."""
    with app.app_context():
        user = create_test_user()
        universe = create_test_tag(name="Terre du Milieu", tag_type="univers")
        character = create_test_character(universe, name="Gandalf", fragments_required=5)
        question = create_test_question(tags=[universe])

        result = award_fragment_for_question(user, question)
        db.session.commit()

        assert result is not None
        assert result[0].id == character.id


def test_award_fragment_targets_the_named_character_in_citation(app):
    """En citation connue, le fragment doit aller au personnage cité."""
    with app.app_context():
        user = create_test_user()
        tag = create_test_tag()
        gandalf = create_test_character(tag, name="Gandalf", fragments_required=5)
        create_test_character(tag, name="Frodo", fragments_required=5)
        question = create_test_question(tags=[tag])

        result = award_fragment_for_question(user, question, character_name="gandalf")
        db.session.commit()

        assert result is not None
        assert result[0].id == gandalf.id


def test_award_fragment_falls_back_when_named_character_unknown(app):
    """Si le personnage cité n'existe pas dans la franchise, on tire au hasard."""
    with app.app_context():
        user = create_test_user()
        tag = create_test_tag()
        character = create_test_character(tag, name="Frodo", fragments_required=5)
        question = create_test_question(tags=[tag])

        result = award_fragment_for_question(user, question, character_name="Personnage Inconnu")
        db.session.commit()

        assert result is not None
        assert result[0].id == character.id


def test_fragment_result_payload_exposes_progress(app):
    """La payload de notification doit exposer le personnage et sa progression."""
    with app.app_context():
        user = create_test_user()
        tag = create_test_tag()
        character = create_test_character(tag, name="Gandalf", fragments_required=5)
        question = create_test_question(tags=[tag])

        result = award_fragment_for_question(user, question)
        payload = fragment_result_payload(user, result)
        db.session.commit()

        assert payload is not None
        assert payload["character_name"] == "Gandalf"
        assert payload["fragments"] == 1
        assert payload["fragments_required"] == 5
        assert payload["progress_percent"] == 20
        assert payload["saga_name"] == "Harry Potter"
        assert "image_x" in payload and "frame_scale" in payload
        assert len(payload["puzzle_grid"]) == 9
        assert payload["character_id"] == character.id
        assert payload["puzzle_new_cells"]  # au moins une case vient d'être révélée

        assert fragment_result_payload(user, None) is None