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


# ---- Codes emoji (payload.visuals) : la modale ET le formulaire pleine
# page doivent pré-remplir la zone de texte, sans quoi rouvrir une question
# emoji pour la modifier repart d'une liste vide -----------------------------

def create_emoji_question() -> Question:
    question = Question(
        mode="emoji",
        prompt="🎬🏰👑",
        payload={"visuals": [
            {"type": "openmoji", "value": "1F3AC"},
            {"type": "openmoji", "value": "1F3F0"},
            {"type": "openmoji", "value": "1F451"},
        ]},
        correct_answer={"film": "The Lion King"},
        requires_account=False,
    )
    db.session.add(question)
    db.session.commit()
    return question


def test_emoji_question_appears_in_the_question_list_thumbnail(client, app):
    """emoji n'a ni affiche ni admin_reference_image : sans ce repli, la
    vignette de la liste retombait sur l'icône générique du mode plutôt que
    sur l'un des indices réellement choisis pour cette question."""
    with app.app_context():
        create_admin()
        question = create_emoji_question()
        question_id = question.id

    login_admin(client, "adminquiz@filmatrix.fr")

    page = client.get("/admin/questions").get_data(as_text=True)

    assert f'id="question-row-{question_id}"' in page
    assert "1F3AC.svg" in page


def test_emoji_question_list_label_reflects_the_actual_visuals_not_the_stale_prompt(client, app):
    """question.prompt (« Texte affiché ») est un champ libre, indépendant de
    payload.visuals : modifier les emojis dans la modale ne le met jamais à
    jour tout seul. Sans un libellé recalculé depuis les vrais indices, la
    liste continuait d'afficher l'ancien texte après avoir changé les
    emojis, ce qui donnait l'impression qu'aucune modification n'était
    enregistrée."""
    with app.app_context():
        create_admin()
        question = create_emoji_question()
        question_id = question.id

    login_admin(client, "adminquiz@filmatrix.fr")

    import json

    client.post(
        f"/admin/questions/{question_id}/modifier",
        data={
            "mode": "emoji",
            "content_type": "film",
            "prompt": "🎬🏰👑",
            "payload": json.dumps({"visuals": [{"type": "openmoji", "value": "1F1EB-1F1F7"}]}),
            "correct_answer": json.dumps({"film": "The Lion King"}),
        },
    )

    page = client.get("/admin/questions").get_data(as_text=True)

    assert f'data-display-text="🇫🇷"' in page
    # question.prompt garde bien "🎬🏰👑" tel quel en base (champ libre, jamais
    # recalculé) - mais ce n'est plus lui que la liste utilise comme libellé.
    assert 'data-display-text="🎬🏰👑"' not in page


def test_modal_edit_form_exposes_emoji_codes(client, app):
    with app.app_context():
        create_admin()
        question = create_emoji_question()
        question_id = question.id

    login_admin(client, "adminquiz@filmatrix.fr")

    page = client.get(
        f"/admin/questions/{question_id}/modifier",
        headers={"X-Requested-With": "XMLHttpRequest"},
    ).get_data(as_text=True)

    assert "1F3AC\n1F3F0\n1F451" in page


def test_fallback_full_page_form_also_exposes_emoji_codes(client, app):
    """Même bug potentiel que pour les images : le formulaire de secours ne
    partage pas le même gabarit que la modale, donc pas automatiquement le
    même pré-remplissage."""
    with app.app_context():
        create_admin()
        question = create_emoji_question()
        question_id = question.id

    login_admin(client, "adminquiz@filmatrix.fr")

    page = client.get(f"/admin/questions/{question_id}/modifier").get_data(as_text=True)

    assert "1F3AC\n1F3F0\n1F451" in page


def test_editing_an_emoji_question_preserves_all_its_codes(client, app):
    """Bout en bout : le JS joint désormais les codes avec un vrai saut de
    ligne (\\n, pas le texte littéral \\\\n) avant l'envoi — ce test simule
    ce qu'il soumet et vérifie que les 3 codes survivent, pas seulement le
    premier."""
    with app.app_context():
        create_admin()
        question = create_emoji_question()
        question_id = question.id

    login_admin(client, "adminquiz@filmatrix.fr")

    import json

    client.post(
        f"/admin/questions/{question_id}/modifier",
        data={
            "mode": "emoji",
            "content_type": "film",
            "prompt": "🎬🏰👑",
            "payload": json.dumps({"visuals": [
                {"type": "openmoji", "value": "1F3AC"},
                {"type": "openmoji", "value": "1F3F0"},
                {"type": "openmoji", "value": "1F451"},
            ]}),
            "correct_answer": json.dumps({"film": "The Lion King"}),
        },
    )

    with app.app_context():
        refreshed = Question.query.get(question_id)
        assert len(refreshed.payload["visuals"]) == 3
        assert [v["value"] for v in refreshed.payload["visuals"]] == ["1F3AC", "1F3F0", "1F451"]


# ---- Édition depuis la modale : rester sur la liste plutôt que de renaviguer
# -----------------------------------------------------------------------------

def test_ajax_edit_returns_json_instead_of_redirecting(client, app):
    """La modale intercepte l'envoi du formulaire et raccroche la ligne à
    jour sur place (voir admin_question_modal.js) : ça suppose que le
    serveur, prévenu par l'en-tête XMLHttpRequest, réponde par un petit JSON
    plutôt que par une redirection vers /admin/questions - sans quoi le JS
    recevrait du HTML de redirection à la place du succès/échec attendu."""
    with app.app_context():
        create_admin()
        question = create_vrai_faux_with_image()
        question_id = question.id

    login_admin(client, "adminquiz@filmatrix.fr")

    import json

    response = client.post(
        f"/admin/questions/{question_id}/modifier",
        headers={"X-Requested-With": "XMLHttpRequest"},
        data={
            "mode": "vrai_faux",
            "content_type": "film",
            "prompt": "Le film Titanic est sorti en 1997. (corrigé)",
            "payload": json.dumps({"question_image_url": "https://images.example/titanic.jpg"}),
            "correct_answer": json.dumps({"value": True}),
        },
    )

    assert response.status_code == 200
    assert response.get_json() == {"success": True}


def test_ajax_edit_with_invalid_json_returns_a_json_error(client, app):
    with app.app_context():
        create_admin()
        question = create_vrai_faux_with_image()
        question_id = question.id

    login_admin(client, "adminquiz@filmatrix.fr")

    import json

    response = client.post(
        f"/admin/questions/{question_id}/modifier",
        headers={"X-Requested-With": "XMLHttpRequest"},
        data={
            "mode": "vrai_faux",
            "content_type": "film",
            "prompt": "peu importe",
            "payload": "{ceci n'est pas du json}",
            "correct_answer": json.dumps({"value": True}),
        },
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body["success"] is False
    assert body["error"]


def test_non_ajax_edit_still_redirects_to_the_questions_list(client, app):
    """Le formulaire de secours en pleine page (sans JS/AJAX) n'a personne
    pour raccrocher une ligne à la volée : il doit garder l'ancien
    comportement (redirection), sans quoi il resterait bloqué sur la
    modale ou recevrait du JSON brut à afficher."""
    with app.app_context():
        create_admin()
        question = create_vrai_faux_with_image()
        question_id = question.id

    login_admin(client, "adminquiz@filmatrix.fr")

    import json

    response = client.post(
        f"/admin/questions/{question_id}/modifier",
        data={
            "mode": "vrai_faux",
            "content_type": "film",
            "prompt": "peu importe",
            "payload": json.dumps({"question_image_url": "https://images.example/titanic.jpg"}),
            "correct_answer": json.dumps({"value": True}),
        },
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin/questions")


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
