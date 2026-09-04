"""Tests de la logique métier de collection de personnages (fragments, déblocage)."""

from filmatrix.catalog_rarities import RARITY_FRAGMENT_COSTS, fragments_for_rarity
from filmatrix.extensions import db
from filmatrix.models import Album, Character, Tag, User, Question
from filmatrix.services.collection import (
    add_fragments,
    award_fragment_for_question,
    fragment_result_payload,
    get_album_summaries,
    get_or_create_progress,
)




def create_test_user(username: str = "Collectionneur") -> User:
    """Crée un utilisateur de test en base"""
    user = User(username=username, email=f"{username.lower()}@filmatrix.fr")
    user.set_password("Azerty1!")
    db.session.add(user)
    db.session.commit()
    return user


def create_test_tag(name: str = "Harry Potter", tag_type: str = "univers") -> Tag:
    """Crée un tag de franchise de test en base"""
    tag = Tag(name=name, tag_type=tag_type)
    db.session.add(tag)
    db.session.commit()
    return tag


def create_test_album(name: str, tags: list[Tag], characters: list[Character]) -> Album:
    """Crée un album lié à des tags et contenant des personnages"""
    album = Album(name=name)
    album.tags = tags
    album.characters = characters
    db.session.add(album)
    db.session.commit()
    return album


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
    """Une question sans tag de franchise (univers) ne doit rien donner."""
    with app.app_context():
        user = create_test_user()
        question = create_test_question()

        result = award_fragment_for_question(user, question)

        assert result is None


def test_award_fragment_returns_none_without_characters(app):
    """Aucun album lié au tag ne doit rien donner."""
    with app.app_context():
        user = create_test_user()
        tag = create_test_tag()
        question = create_test_question(tags=[tag])

        result = award_fragment_for_question(user, question)

        assert result is None


def test_award_fragment_gives_fragment_to_locked_character(app):
    """Une bonne réponse doit donner un fragment à un personnage verrouillé de l'album."""
    with app.app_context():
        user = create_test_user()
        tag = create_test_tag()
        character = create_test_character(tag, fragments_required=5)
        create_test_album("Album Test", [tag], [character])
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
        create_test_album("Album Test", [tag], [character])
        question = create_test_question(tags=[tag])

        award_fragment_for_question(user, question)
        db.session.commit()

        result = award_fragment_for_question(user, question)

        assert result is None


def test_award_fragment_targets_univers_tag(app):
    """Une question liée à un tag « univers » doit alimenter l'album correspondant."""
    with app.app_context():
        user = create_test_user()
        universe = create_test_tag(name="Terre du Milieu", tag_type="univers")
        character = create_test_character(universe, name="Gandalf", fragments_required=5)
        create_test_album("Terre du Milieu", [universe], [character])
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
        create_test_album("Album Test", [tag], [gandalf])
        question = create_test_question(tags=[tag])

        result = award_fragment_for_question(user, question, character_name="gandalf")
        db.session.commit()

        assert result is not None
        assert result[0].id == gandalf.id


def test_award_fragment_falls_back_when_named_character_unknown(app):
    """Si le personnage cité n'existe pas dans l'album, on tire au hasard."""
    with app.app_context():
        user = create_test_user()
        tag = create_test_tag()
        character = create_test_character(tag, name="Frodo", fragments_required=5)
        create_test_album("Album Test", [tag], [character])
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
        create_test_album("Album Test", [tag], [character])
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
        # La grille colle au vrai nombre de fragments requis (5 ici), pas à
        # un 3x3 fixe : voir puzzle.py, grid_size_for.
        assert len(payload["puzzle_grid"]) == 5
        assert payload["puzzle_columns"] == 3
        assert payload["character_id"] == character.id
        assert payload["puzzle_new_cells"]  # au moins une case vient d'être révélée

        assert fragment_result_payload(user, None) is None


def test_award_fragment_prefers_the_most_specific_album(app):
    """Un album lié à un univers doit passer avant un album de genre."""
    with app.app_context():
        user = create_test_user()
        genre = create_test_tag(name="Horreur", tag_type="genre")
        univers = create_test_tag(name="American Horror Story", tag_type="univers")
        genre_char = create_test_character(genre, name="Art", fragments_required=5)
        univers_char = create_test_character(univers, name="Violet", fragments_required=5)
        create_test_album("Horreur", [genre], [genre_char])
        create_test_album("American Horror Story", [univers], [univers_char])
        question = create_test_question(tags=[genre, univers])

        result = award_fragment_for_question(user, question)
        db.session.commit()

        assert result is not None
        assert result[0].id == univers_char.id


def test_collection_routes_render(app, client):
    """La collection (vue d'ensemble, album, profil) doit se rendre sans erreur."""
    with app.app_context():
        user = create_test_user()
        tag = create_test_tag()
        char = create_test_character(tag, fragments_required=5)
        album = create_test_album("Album Test", [tag], [char])
        album_id = album.id

    client.post(
        "/connexion",
        data={"email": "collectionneur@filmatrix.fr", "password": "Azerty1!"},
    )

    assert client.get("/collection").status_code == 200
    assert client.get(f"/collection/{album_id}").status_code == 200
    assert client.get("/profil").status_code == 200


def test_get_album_summaries_reports_progress(app):
    """Le résumé d'album doit compter les personnages débloqués et la vignette vedette."""
    with app.app_context():
        user = create_test_user()
        tag = create_test_tag()
        unlocked = create_test_character(tag, name="Gandalf", fragments_required=2)
        locked = create_test_character(tag, name="Frodo", fragments_required=5)
        create_test_album("Album Test", [tag], [unlocked, locked])

        add_fragments(user, unlocked, 2)
        db.session.commit()

        summaries = get_album_summaries(user)
        assert len(summaries) == 1
        summary = summaries[0]
        assert summary["name"] == "Album Test"
        assert summary["unlocked_count"] == 1
        assert summary["total_count"] == 2
        assert summary["image_url"] == unlocked.image_url


def test_rarity_fragment_costs_ladder_is_ordered():
    """Le barème doit être croissant avec la rareté et plafonné à la grille (9)."""
    ladder = [
        RARITY_FRAGMENT_COSTS["commun"],
        RARITY_FRAGMENT_COSTS["rare"],
        RARITY_FRAGMENT_COSTS["epique"],
        RARITY_FRAGMENT_COSTS["legendaire"],
        RARITY_FRAGMENT_COSTS["mythique"],
    ]
    assert ladder == sorted(ladder)
    assert all(1 <= cost <= 9 for cost in ladder)


def test_fragments_for_rarity_falls_back_on_unknown_rarity():
    """Une rareté inconnue retombe sur la valeur de repli sans planter."""
    assert fragments_for_rarity("inconnue", fallback=5) == 5
    assert fragments_for_rarity("commun") == RARITY_FRAGMENT_COSTS["commun"]


def test_character_creation_falls_back_to_rarity_scale_on_missing_field(client, app):
    """Sans champ fragments_required, la route doit appliquer le barème de la rareté."""
    with app.app_context():
        admin = User(username="AdminFrag", email="adminfrag@filmatrix.fr", is_admin=True)
        admin.set_password("Azerty1!")
        db.session.add(admin)
        tag = create_test_tag(name="Test Frag")
        tag_id = tag.id
        db.session.commit()

    client.post("/connexion", data={"email": "adminfrag@filmatrix.fr", "password": "Azerty1!"})

    response = client.post(
        "/admin/personnages/nouveau",
        data={
            "name": "Perso Sans Champ",
            "tag_id": tag_id,
            "rarity": "mythique",
            # pas de fragments_required : le serveur doit appliquer le barème
        },
    )
    assert response.status_code == 302

    with app.app_context():
        character = Character.query.filter_by(name="Perso Sans Champ").first()
        assert character is not None
        assert character.fragments_required == RARITY_FRAGMENT_COSTS["mythique"]


def test_character_creation_keeps_explicit_fragments_field(client, app):
    """Un champ fragments_required explicite doit être respecté (mode manuel)."""
    with app.app_context():
        admin = User(username="AdminFrag2", email="adminfrag2@filmatrix.fr", is_admin=True)
        admin.set_password("Azerty1!")
        db.session.add(admin)
        tag = create_test_tag(name="Test Frag 2")
        tag_id = tag.id
        db.session.commit()

    client.post("/connexion", data={"email": "adminfrag2@filmatrix.fr", "password": "Azerty1!"})

    response = client.post(
        "/admin/personnages/nouveau",
        data={
            "name": "Perso Manuel",
            "tag_id": tag_id,
            "rarity": "commun",
            "fragments_required": "4",
        },
    )
    assert response.status_code == 302

    with app.app_context():
        character = Character.query.filter_by(name="Perso Manuel").first()
        assert character is not None
        assert character.fragments_required == 4
