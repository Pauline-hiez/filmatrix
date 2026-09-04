"""Tests de la préservation des images (qcm/vrai_faux) dans le formulaire admin.

Le formulaire reconstruit tout le payload à l'envoi depuis les champs
visibles (voir buildPayloadAndAnswer dans admin_question_form.js) : sans un
champ caché dédié, question_image_url et option_images — posés par
l'enrichissement TMDB, jamais saisis à la main — disparaissaient à chaque
enregistrement. Ces tests couvrent la moitié serveur du correctif (le
gabarit doit bien exposer ces valeurs) ; la reconstruction du payload
elle-même est du JS, vérifié séparément par node --check.
"""

from filmatrix.extensions import db
from filmatrix.models import Question, User


def create_admin(username: str = "AdminQuiz") -> User:
    admin = User(username=username, email=f"{username.lower()}@filmatrix.fr", is_admin=True)
    admin.set_password("Azerty1!")
    db.session.add(admin)
    db.session.commit()
    return admin


def login_admin(client, email: str) -> None:
    client.post("/connexion", data={"email": email, "password": "Azerty1!"})


def create_qcm_with_images() -> Question:
    question = Question(
        mode="qcm",
        prompt="Dans quel film ?",
        payload={
            "options": ["A", "B", "C", "D"],
            "question_image_url": "https://images.example/context.jpg",
            "option_images": ["https://images.example/a.jpg", None, "https://images.example/c.jpg", None],
        },
        correct_answer={"index": 0},
        requires_account=False,
    )
    db.session.add(question)
    db.session.commit()
    return question


def create_vrai_faux_with_image() -> Question:
    question = Question(
        mode="vrai_faux",
        prompt="Le film Titanic est sorti en 1997.",
        payload={"question_image_url": "https://images.example/titanic.jpg"},
        correct_answer={"value": True},
        requires_account=False,
    )
    db.session.add(question)
    db.session.commit()
    return question


def test_modal_edit_form_exposes_qcm_images(client, app):
    """La modale d'édition (flux principal) doit exposer l'affiche de
    contexte et les images par option dans des champs cachés, pas seulement
    les montrer : ce sont eux qui les feront survivre au prochain
    enregistrement."""
    with app.app_context():
        create_admin()
        question = create_qcm_with_images()
        question_id = question.id

    login_admin(client, "adminquiz@filmatrix.fr")

    page = client.get(
        f"/admin/questions/{question_id}/modifier",
        headers={"X-Requested-With": "XMLHttpRequest"},
    ).get_data(as_text=True)

    assert 'class="question-image-url" value="https://images.example/context.jpg"' in page
    assert "https://images.example/context.jpg" in page  # aperçu <img>
    assert 'class="qcm-option-image" value="https://images.example/a.jpg"' in page
    assert 'class="qcm-option-image" value="https://images.example/c.jpg"' in page


def test_modal_edit_form_exposes_vrai_faux_image(client, app):
    with app.app_context():
        create_admin()
        question = create_vrai_faux_with_image()
        question_id = question.id

    login_admin(client, "adminquiz@filmatrix.fr")

    page = client.get(
        f"/admin/questions/{question_id}/modifier",
        headers={"X-Requested-With": "XMLHttpRequest"},
    ).get_data(as_text=True)

    assert 'class="question-image-url" value="https://images.example/titanic.jpg"' in page


def test_fallback_full_page_form_also_exposes_qcm_images(client, app):
    """Le formulaire pleine page (secours quand la requête n'est pas AJAX)
    doit exposer les mêmes champs, pas seulement la modale."""
    with app.app_context():
        create_admin()
        question = create_qcm_with_images()
        question_id = question.id

    login_admin(client, "adminquiz@filmatrix.fr")

    page = client.get(f"/admin/questions/{question_id}/modifier").get_data(as_text=True)

    assert 'class="question-image-url" value="https://images.example/context.jpg"' in page
    assert 'class="qcm-option-image" value="https://images.example/a.jpg"' in page


def test_editing_a_qcm_question_preserves_its_images(client, app):
    """Bout en bout : simuler ce que le JS soumet désormais (avec les champs
    images) et vérifier que la base garde bien les images après coup —
    c'était le vrai bug (elles étaient silencieusement effacées)."""
    with app.app_context():
        create_admin()
        question = create_qcm_with_images()
        question_id = question.id

    login_admin(client, "adminquiz@filmatrix.fr")

    import json

    client.post(
        f"/admin/questions/{question_id}/modifier",
        data={
            "mode": "qcm",
            "content_type": "film",
            "prompt": "Dans quel film ? (corrigé)",
            "payload": json.dumps(
                {
                    "options": ["A", "B", "C", "D"],
                    "question_image_url": "https://images.example/context.jpg",
                    "option_images": ["https://images.example/a.jpg", None, "https://images.example/c.jpg", None],
                }
            ),
            "correct_answer": json.dumps({"index": 0}),
        },
    )

    with app.app_context():
        refreshed = Question.query.get(question_id)
        assert refreshed.prompt == "Dans quel film ? (corrigé)"
        assert refreshed.payload["question_image_url"] == "https://images.example/context.jpg"
        assert refreshed.payload["option_images"][0] == "https://images.example/a.jpg"


def test_editing_a_qcm_question_without_the_image_fields_loses_them(client, app):
    """Documente le bug d'origine : si le payload envoyé ne porte pas ces
    clés (comme avant le correctif JS), elles sont bel et bien perdues — ce
    test sert de garde-fou pour ne pas réintroduire silencieusement le bug
    ailleurs (ex. un autre point d'entrée qui oublierait ces champs)."""
    with app.app_context():
        create_admin()
        question = create_qcm_with_images()
        question_id = question.id

    login_admin(client, "adminquiz@filmatrix.fr")

    import json

    client.post(
        f"/admin/questions/{question_id}/modifier",
        data={
            "mode": "qcm",
            "content_type": "film",
            "prompt": "Dans quel film ?",
            "payload": json.dumps({"options": ["A", "B", "C", "D"]}),
            "correct_answer": json.dumps({"index": 0}),
        },
    )

    with app.app_context():
        refreshed = Question.query.get(question_id)
        assert "question_image_url" not in refreshed.payload


# ---- Repère interne (admin_reference_image) : citation/devinette/
# film_melange/blindtest, qui n'ont sinon aucun visuel côté admin --------

def create_citation_with_reference() -> Question:
    question = Question(
        mode="citation",
        prompt="«I'll be back.» De quel film vient cette réplique ?",
        payload={"admin_reference_image": "https://images.example/terminator-admin.jpg"},
        correct_answer={"film": "Terminator"},
        requires_account=False,
    )
    db.session.add(question)
    db.session.commit()
    return question


def test_admin_reference_image_appears_in_the_edit_form(client, app):
    with app.app_context():
        create_admin()
        question = create_citation_with_reference()
        question_id = question.id

    login_admin(client, "adminquiz@filmatrix.fr")

    page = client.get(
        f"/admin/questions/{question_id}/modifier",
        headers={"X-Requested-With": "XMLHttpRequest"},
    ).get_data(as_text=True)

    assert "https://images.example/terminator-admin.jpg" in page
    assert 'class="admin-reference-image" value="https://images.example/terminator-admin.jpg"' in page
    assert "Repère interne" in page


def test_admin_reference_image_appears_in_the_question_list_thumbnail(client, app):
    """citation n'a par ailleurs aucune autre source d'image : sans ce
    champ, la vignette de la liste retombait sur l'icône générique du mode."""
    with app.app_context():
        create_admin()
        question = create_citation_with_reference()
        question_id = question.id

    login_admin(client, "adminquiz@filmatrix.fr")

    page = client.get("/admin/questions").get_data(as_text=True)

    assert f'id="question-row-{question_id}"' in page
    assert "https://images.example/terminator-admin.jpg" in page


def test_editing_a_citation_question_preserves_its_reference_image(client, app):
    """Même bug que pour qcm/vrai_faux, même correctif : sans le hidden, ce
    champ disparaîtrait au prochain enregistrement."""
    with app.app_context():
        create_admin()
        question = create_citation_with_reference()
        question_id = question.id

    login_admin(client, "adminquiz@filmatrix.fr")

    import json

    client.post(
        f"/admin/questions/{question_id}/modifier",
        data={
            "mode": "citation",
            "content_type": "film",
            "prompt": "«I'll be back.» De quel film vient cette réplique ? (corrigé)",
            "payload": json.dumps({"admin_reference_image": "https://images.example/terminator-admin.jpg"}),
            "correct_answer": json.dumps({"film": "Terminator"}),
        },
    )

    with app.app_context():
        refreshed = Question.query.get(question_id)
        assert refreshed.payload["admin_reference_image"] == "https://images.example/terminator-admin.jpg"


def test_admin_reference_image_never_leaks_to_the_player_facing_render(app):
    """Filet de sécurité : même présent en payload, admin_reference_image ne
    doit jamais être ce que question_image_url() renvoie pour un joueur —
    citation reste sur l'icône générique du mode, jamais l'affiche réelle."""
    from filmatrix.services.questions import question_image_url

    with app.test_request_context():
        question = create_citation_with_reference()

        url = question_image_url(question)

        assert url is not None
        assert "terminator-admin" not in url
        assert url.endswith("/images/icones/citation.png")
