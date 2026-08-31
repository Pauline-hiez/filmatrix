"""Tests de la logique métier de collection de personnages (fragments, déblocage)."""

from filmatrix.extensions import db
from filmatrix.models import Character, Tag, User
from filmatrix.services.collection import add_fragments, get_characters_for_tag, get_or_create_progress


def create_test_user(username: str = "Collectionneur") -> User:
    """Crée un utilisateur de test en base"""
    user = User(username=username, email=f"{username.lower()}@filmatrix.fr")
    user.set_password("Azerty1!")
    db.session.add(user)
    db.session.commit()
    return user


def create_test_tag(name: str = "Harry Potter") -> Tag:
    """Crée un tag de saga de test en base"""
    tag = Tag(name=name, tag_type="saga")
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