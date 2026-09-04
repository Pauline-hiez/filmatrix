"""Tests de l'humanisation des noms de tags stockés en slug."""

from filmatrix.catalog_rarities import humanize_tag_name
from filmatrix.extensions import db
from filmatrix.models import Question, Tag, User


def test_simple_dash_slug_is_title_cased():
    assert humanize_tag_name("indiana-jones") == "Indiana Jones"


def test_single_word_slug_is_capitalized():
    """Un tag sans tiret (ex. un genre) doit aussi être capitalisé, pas
    seulement les slugs multi-mots reliés par des tirets."""
    assert humanize_tag_name("comedie") == "Comedie"
    assert humanize_tag_name("horreur") == "Horreur"


def test_country_names_get_their_accents_and_hyphen():
    """Un titre mot à mot ne suffit pas pour ces cas : États-Unis a un
    accent et un trait d'union qu'un simple .title() ne devine pas."""
    assert humanize_tag_name("etats-unis") == "États-Unis"
    assert humanize_tag_name("royaume-uni") == "Royaume-Uni"
    assert humanize_tag_name("nouvelle-zelande") == "Nouvelle-Zélande"
    assert humanize_tag_name("coree-du-sud") == "Corée du Sud"


def test_acronyms_are_uppercased_not_title_cased():
    assert humanize_tag_name("hbo") == "HBO"


def test_particles_stay_lowercase_mid_name():
    assert humanize_tag_name("guillermo-del-toro") == "Guillermo del Toro"
    assert humanize_tag_name("robert-de-niro") == "Robert De Niro"


def test_already_humanized_name_is_left_untouched():
    """Un nom déjà lisible (espace ou majuscule présente) ne doit jamais être
    retouché : ce n'est pas un slug d'import, une majuscule mal placée
    déformerait un nom déjà correct."""
    assert humanize_tag_name("Indiana Jones") == "Indiana Jones"
    assert humanize_tag_name("États-Unis") == "États-Unis"


def test_humanize_is_idempotent():
    """Appliquer la fonction deux fois de suite ne doit rien changer de plus,
    important puisqu'elle tourne maintenant à chaque affichage."""
    once = humanize_tag_name("etats-unis")
    twice = humanize_tag_name(once)
    assert once == twice


def create_test_user(username: str = "Joueur") -> User:
    user = User(username=username, email=f"{username.lower()}@filmatrix.fr")
    user.set_password("Azerty1!")
    db.session.add(user)
    db.session.commit()
    return user


def test_preparation_screen_shows_humanized_tag_names(client, app):
    """La donnée peut rester en slug en base (ex. environnement où la
    migration scripts/humanize_tag_slugs.py n'a jamais tourné, comme la
    production) : l'écran de préparation doit quand même l'afficher lisible."""
    with app.app_context():
        create_test_user()
        genre_tag = Tag(name="comedie", tag_type="genre")
        univers_tag = Tag(name="etats-unis", tag_type="pays")
        db.session.add_all([genre_tag, univers_tag])
        db.session.commit()

        # Un tag n'apparaît dans le sélecteur qu'à partir de 5 questions au
        # total (DEFAULT_TAG_MIN_QUESTIONS, filmatrix/services/questions.py) :
        # il en faut au moins 5 pour que ces deux tags soient bien listés.
        for index in range(5):
            question = Question(
                mode="qcm",
                prompt=f"Question test {index}",
                payload={"options": ["A", "B"]},
                correct_answer={"index": 0},
                requires_account=False,
            )
            question.tags = [genre_tag, univers_tag]
            db.session.add(question)
        db.session.commit()

    client.post("/connexion", data={"email": "joueur@filmatrix.fr", "password": "Azerty1!"})

    page = client.get("/quiz/qcm").get_data(as_text=True)

    assert "Comedie" in page
    assert "États-Unis" in page
    assert "etats-unis" not in page
    assert ">comedie<" not in page
