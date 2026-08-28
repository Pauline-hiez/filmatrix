"""Sélection des questions d'une partie solo.

Ces fonctions vivaient dans create_app(), imbriquées dans la fabrique de
l'application : elles y étaient inaccessibles aux tests comme aux blueprints.
Elles ne dépendent que du modèle et de la session, leur place est ici.
"""

import random

from flask import session
from flask_login import current_user

from filmatrix.models import Question, Tag
from filmatrix.services.score import QUESTIONS_PER_RUN, run_question_id


def resolve_content_type(value: str | None) -> str:
    """Normalise les libellés de contenu utilisés par l'interface."""
    aliases = {"film": "film", "films": "film", "serie": "serie", "série": "serie", "series": "serie", "séries": "serie"}
    return aliases.get((value or "").strip().lower(), "")

def build_question_query(
    mode: str,
    tag_id: int | None = None,
    content_type: str | None = None,
    tag_ids: list[int] | None = None,
):
    """Construit la requête des questions jouables pour un mode et ses filtres

    L'ordre est fixé par l'id : deux appels successifs pour la même partie
    doivent renvoyer les questions dans le même ordre, sans quoi le joueur
    rejouerait la même à des positions différentes"""
    query = Question.query.filter_by(mode=mode)

    selected_tag_ids = tag_ids if tag_ids is not None else ([tag_id] if tag_id else [])
    for selected_tag_id in selected_tag_ids:
        query = query.filter(Question.tags.any(Tag.id == selected_tag_id))

    if content_type:
        query = query.filter_by(content_type=content_type)

    return query.order_by(Question.id)

def playable_question_query(
    mode: str,
    tag_id: int | None = None,
    content_type: str | None = None,
    tag_ids: list[int] | None = None,
):
    """Restreint aux questions que le joueur peut réellement jouer

    Une question réservée aux comptes renverrait un visiteur vers la page de
    connexion en pleine partie, sa progression perdue : elle n'a rien à faire
    ni dans le tirage, ni dans les compteurs qu'on lui annonce"""
    query = build_question_query(mode, tag_id, content_type, tag_ids)

    if not current_user.is_authenticated:
        query = query.filter_by(requires_account=False)

    return query

def count_run_questions(
    mode: str,
    tag_id: int | None = None,
    content_type: str | None = None,
    tag_ids: list[int] | None = None,
) -> int:
    """Retourne le nombre de questions que comptera la partie

    Une partie fait QUESTIONS_PER_RUN questions, sauf si les filtres du
    joueur en laissent moins : on ne promet pas un total qu'on ne peut pas
    servir"""
    available = playable_question_query(mode, tag_id, content_type, tag_ids).count()
    return min(QUESTIONS_PER_RUN, available)

def run_filters(
    tag_id: int | None = None,
    content_type: str | None = None,
    tag_ids: list[int] | None = None,
) -> dict:
    """Décrit les réglages d'une partie, sous une forme rangeable en session"""
    normalized_tag_ids = tag_ids if tag_ids is not None else ([tag_id] if tag_id else [])
    return {"tag_ids": normalized_tag_ids, "content_type": content_type}

def draw_run_questions(
    mode: str,
    tag_id: int | None = None,
    content_type: str | None = None,
    tag_ids: list[int] | None = None,
) -> list[int]:
    """Tire au sort les questions d'une nouvelle partie

    Le tirage a lieu une seule fois, au lancement : deux parties du même mode
    ne se ressemblent pas, mais à l'intérieur d'une partie l'ordre ne bouge
    plus, sans quoi avancer d'une question en ramènerait une déjà posée"""
    question_ids = [
        row.id for row in playable_question_query(mode, tag_id, content_type, tag_ids).all()
    ]
    random.shuffle(question_ids)

    return question_ids[:QUESTIONS_PER_RUN]

def find_question(
    mode: str,
    position: int,
    tag_id: int | None = None,
    content_type: str | None = None,
    tag_ids: list[int] | None = None,
):
    """Cherche la question à une position donnée, parmi celles d'un mode, tag et type de contenu

    Renvoie None au-delà de la dernière position de la partie : c'est ce qui
    met fin à la partie et renvoie le joueur vers l'écran de score"""
    if position < 1 or position > QUESTIONS_PER_RUN:
        return None

    filters = run_filters(tag_id, content_type, tag_ids)
    question_id = run_question_id(session, mode, position, filters)

    if question_id is not None:
        return Question.query.get(question_id)

    # Aucun tirage en session : lien direct vers une question, session
    # expirée ou navigation manuelle. On sert alors l'ordre stable par id,
    # plutôt que de refuser la question au joueur.
    query = build_question_query(mode, tag_id, content_type, tag_ids)

    return query.offset(position - 1).limit(1).first()

def shuffle_options(question) -> list[tuple[int, str]]:
    """Mélange les propositions d'un QCM, chacune gardant son index d'origine

    La bonne réponse est l'option 0 dans la majorité des questions : sans
    mélange, le joueur finit par répondre au réflexe. C'est bien l'index
    d'origine qui repart au serveur, la vérification reste donc inchangée"""
    options = list(enumerate(question.payload["options"]))
    random.shuffle(options)

    return options


def format_correct_answer(question) -> str:
    """Formate la bonne réponse d'une question en texte lisible pour tous les modes"""
    if question.mode == "qcm":
        index = question.correct_answer["index"]
        return question.payload["options"][index]
    if question.mode == "vrai_faux":
        return  "Vrai" if question.correct_answer["value"] else "Faux"
    if question.mode == "chronologie":
        return "→".join(question.correct_answer["order"])
    return question.correct_answer.get("film") or question.correct_answer.get("title") or ""
