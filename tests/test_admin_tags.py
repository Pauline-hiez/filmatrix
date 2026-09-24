"""Tests de la gestion curatée des tags univers (renommage, fusion)."""

from datetime import date

from filmatrix.extensions import db
from filmatrix.models import Character, DailyChallenge, Question, QuestionSubmission, Tag, User


def create_admin(username: str = "AdminTags", email: str = "admintags@filmatrix.fr") -> User:
    admin = User(username=username, email=email, is_admin=True)
    admin.set_password("Azerty1!")
    db.session.add(admin)
    db.session.commit()
    return admin


def login_admin(client, email: str = "admintags@filmatrix.fr") -> None:
    client.post("/connexion", data={"email": email, "password": "Azerty1!"})


def create_tag(name: str, tag_type: str = "univers") -> Tag:
    tag = Tag(name=name, tag_type=tag_type)
    db.session.add(tag)
    db.session.commit()
    return tag


def test_admin_tags_new_rejects_case_insensitive_duplicate(client, app):
    """Créer 'star wars' quand 'Star Wars' existe déjà doit être refusé, pas planter."""
    with app.app_context():
        create_admin()
        create_tag("Star Wars")

    login_admin(client)
    response = client.post(
        "/admin/tags/nouveau", data={"name": "star wars", "tag_type": "univers"}
    )
    assert response.status_code == 302

    with app.app_context():
        assert Tag.query.filter_by(tag_type="univers").count() == 1


def test_admin_tags_new_allows_same_name_across_different_types(client, app):
    """'Halloween' doit pouvoir exister à la fois en univers (la franchise de
    films) et en thème (la période) : le nom n'est unique que par type."""
    with app.app_context():
        create_admin()
        create_tag("Halloween", tag_type="univers")

    login_admin(client)
    response = client.post(
        "/admin/tags/nouveau", data={"name": "Halloween", "tag_type": "theme"}
    )
    assert response.status_code == 302

    with app.app_context():
        assert Tag.query.filter_by(name="Halloween", tag_type="univers").count() == 1
        assert Tag.query.filter_by(name="Halloween", tag_type="theme").count() == 1


def test_admin_tags_rename_updates_name(client, app):
    with app.app_context():
        create_admin()
        tag = create_tag("Kaamelot")
        tag_id = tag.id

    login_admin(client)
    response = client.post(f"/admin/tags/{tag_id}/renommer", data={"name": "Kaamelott"})
    assert response.status_code == 302

    with app.app_context():
        assert Tag.query.get(tag_id).name == "Kaamelott"


def test_admin_tags_rename_rejects_case_insensitive_collision(client, app):
    with app.app_context():
        create_admin()
        other = create_tag("Halloween")
        dup = create_tag("Hallowen")
        dup_id = dup.id

    login_admin(client)
    client.post(f"/admin/tags/{dup_id}/renommer", data={"name": "halloween"})

    with app.app_context():
        # Le renommage est refusé : le nom d'origine (fautif) est conservé.
        assert Tag.query.get(dup_id).name == "Hallowen"
        assert Tag.query.filter_by(tag_type="univers").count() == 2


def test_admin_tags_merge_reassigns_questions_characters_and_challenges(client, app):
    with app.app_context():
        admin = create_admin()
        keeper = create_tag("Star Wars")
        dup = create_tag("star-wars")

        question = Question(
            mode="citation", prompt="Test", payload={}, correct_answer={"film": "Star Wars"},
        )
        question.tags = [dup]
        db.session.add(question)

        character = Character(name="Yoda", tag_id=dup.id, rarity="rare", fragments_required=5)
        db.session.add(character)

        challenge = DailyChallenge(
            user_id=admin.id, challenge_date=date(2026, 1, 1), challenge_type="saga_count",
            target_value=3, target_tag_id=dup.id,
        )
        db.session.add(challenge)
        db.session.commit()

        keeper_id, dup_id, question_id, character_id, challenge_id = (
            keeper.id, dup.id, question.id, character.id, challenge.id,
        )

    login_admin(client)
    response = client.post(
        "/admin/tags/fusionner", data={"keeper_id": keeper_id, "dup_id": dup_id}
    )
    assert response.status_code == 302

    with app.app_context():
        assert Tag.query.get(dup_id) is None
        assert Tag.query.get(keeper_id) is not None
        assert Question.query.get(question_id).tags == [Tag.query.get(keeper_id)]
        assert Character.query.get(character_id).tag_id == keeper_id
        assert DailyChallenge.query.get(challenge_id).target_tag_id == keeper_id


def test_admin_tags_rename_allows_collision_with_a_different_type(client, app):
    """Renommer un tag Thème en 'Halloween' doit fonctionner même si un tag
    Univers du même nom existe déjà : ce n'est un doublon que dans le même type."""
    with app.app_context():
        create_admin()
        create_tag("Halloween", tag_type="univers")
        theme_tag = create_tag("Fetes d'automne", tag_type="theme")
        theme_id = theme_tag.id

    login_admin(client)
    response = client.post(f"/admin/tags/{theme_id}/renommer", data={"name": "Halloween"})
    assert response.status_code == 302

    with app.app_context():
        assert Tag.query.get(theme_id).name == "Halloween"


def test_admin_tags_merge_refuses_non_univers_types(client, app):
    with app.app_context():
        create_admin()
        keeper = create_tag("Horreur", tag_type="genre")
        dup = create_tag("horreur", tag_type="genre")
        keeper_id, dup_id = keeper.id, dup.id

    login_admin(client)
    client.post("/admin/tags/fusionner", data={"keeper_id": keeper_id, "dup_id": dup_id})

    with app.app_context():
        assert Tag.query.get(dup_id) is not None


def test_admin_tags_merge_works_for_theme_tags(client, app):
    with app.app_context():
        create_admin()
        keeper = create_tag("Halloween", tag_type="theme")
        dup = create_tag("halloween", tag_type="theme")
        keeper_id, dup_id = keeper.id, dup.id

    login_admin(client)
    response = client.post("/admin/tags/fusionner", data={"keeper_id": keeper_id, "dup_id": dup_id})
    assert response.status_code == 302

    with app.app_context():
        assert Tag.query.get(dup_id) is None
        assert Tag.query.get(keeper_id) is not None


def test_admin_tags_delete_cleans_up_pending_submission_associations(client, app):
    """Supprimer un tag encore porté par une suggestion en attente ne doit pas
    laisser de ligne orpheline dans submission_tags/submission_reviewed_tags
    (incident réel : QuestionSubmission.tags n'avait pas de backref vers Tag,
    donc l'ORM ne savait pas nettoyer ces deux tables à la suppression)."""
    with app.app_context():
        admin = create_admin()
        tag = create_tag("Halloween", tag_type="theme")

        submission = QuestionSubmission(
            user_id=admin.id, status="pending", mode="qcm", prompt="Test",
            payload={"options": ["A", "B", "C", "D"]}, correct_answer={"index": 0},
        )
        submission.tags = [tag]
        submission.reviewed_tags = [tag]
        db.session.add(submission)
        db.session.commit()

        tag_id, submission_id = tag.id, submission.id

    login_admin(client)
    response = client.post(f"/admin/tags/{tag_id}/supprimer")
    assert response.status_code == 302

    with app.app_context():
        assert Tag.query.get(tag_id) is None
        # La suggestion elle-même doit survivre, juste sans ce tag.
        assert QuestionSubmission.query.get(submission_id).tags == []
        assert QuestionSubmission.query.get(submission_id).reviewed_tags == []


def test_admin_tags_merge_reassigns_pending_submission_tags(client, app):
    """Une suggestion encore en attente (pas seulement une question publiée)
    doit aussi voir son tag réassigné - sans quoi la ligne supprimée avec le
    tag fusionné laisserait une association orpheline (incident réel)."""
    with app.app_context():
        admin = create_admin()
        keeper = create_tag("Halloween", tag_type="theme")
        dup = create_tag("halloween", tag_type="theme")

        submission = QuestionSubmission(
            user_id=admin.id, status="pending", mode="qcm", prompt="Test",
            payload={"options": ["A", "B", "C", "D"]}, correct_answer={"index": 0},
        )
        submission.tags = [dup]
        db.session.add(submission)
        db.session.commit()

        keeper_id, dup_id, submission_id = keeper.id, dup.id, submission.id

    login_admin(client)
    response = client.post("/admin/tags/fusionner", data={"keeper_id": keeper_id, "dup_id": dup_id})
    assert response.status_code == 302

    with app.app_context():
        assert Tag.query.get(dup_id) is None
        assert QuestionSubmission.query.get(submission_id).tags == [Tag.query.get(keeper_id)]
