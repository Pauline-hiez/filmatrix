"""Sélection des questions d'une partie solo.

Ces fonctions vivaient dans create_app(), imbriquées dans la fabrique de
l'application : elles y étaient inaccessibles aux tests comme aux blueprints.
Elles ne dépendent que du modèle et de la session, leur place est ici.
"""

import random

from flask import session
from flask_login import current_user
from sqlalchemy import func

from filmatrix.extensions import db
from filmatrix.game_modes import MIX_MODE_SLUG
from filmatrix.models import Question, Tag, question_tags
from filmatrix.services.score import QUESTIONS_PER_RUN, run_question_id

# En dessous de ce nombre de questions (toutes comptées sur l'ensemble du
# catalogue, pas seulement dans le mode consulté), un tag encombre le
# sélecteur sans offrir de filtrage réellement utile : univers et saga
# accumulent vite des entrées nées d'une unique mention. Univers a son propre
# seuil, plus haut, car il concentre à lui seul l'essentiel de ces mentions
# isolées.
TAG_MIN_QUESTIONS = {"univers": 20}
DEFAULT_TAG_MIN_QUESTIONS = 5


def mode_tags(mode: str) -> list[Tag]:
    """Liste les tags proposés sur l'écran de préparation d'un mode

    Un tag n'est montré que s'il a au moins une question dans ce mode (sans
    quoi le joueur choisirait un filtre qui ne renvoie rien), et seulement
    s'il compte assez de questions au total pour valoir la peine d'être
    proposé (cf. TAG_MIN_QUESTIONS). Le mode mix pioche parmi toutes les
    questions, quel que soit leur mode : un tag y est donc listé sans
    restriction de mode."""
    tag_condition = (
        Tag.questions.any() if mode == MIX_MODE_SLUG else Tag.questions.any(Question.mode == mode)
    )
    candidates = Tag.query.filter(tag_condition).all()
    if not candidates:
        return []

    global_counts = dict(
        db.session.query(question_tags.c.tag_id, func.count(question_tags.c.question_id))
        .filter(question_tags.c.tag_id.in_([tag.id for tag in candidates]))
        .group_by(question_tags.c.tag_id)
        .all()
    )

    kept = [
        tag
        for tag in candidates
        if global_counts.get(tag.id, 0) >= TAG_MIN_QUESTIONS.get(tag.tag_type, DEFAULT_TAG_MIN_QUESTIONS)
    ]
    return sorted(kept, key=lambda tag: (tag.tag_type, tag.name))


def mode_tags_for_type(mode: str, tag_type: str) -> list[Tag]:
    """Liste tous les tags d'un type donné utilisables dans un mode, sans le
    seuil de popularité de mode_tags()

    Réservé au lien « voir tous les univers » de l'écran de préparation :
    l'utilisateur qui cherche précisément un univers peu fourni doit pouvoir
    le retrouver, même s'il n'apparaît pas dans la liste proposée par défaut."""
    tag_condition = (
        Tag.questions.any() if mode == MIX_MODE_SLUG else Tag.questions.any(Question.mode == mode)
    )
    return (
        Tag.query.filter(tag_condition, Tag.tag_type == tag_type)
        .order_by(Tag.name)
        .all()
    )


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
    rejouerait la même à des positions différentes. Le mode mix pioche parmi
    toutes les questions, quel que soit leur mode réel."""
    query = Question.query if mode == MIX_MODE_SLUG else Question.query.filter_by(mode=mode)

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

DRAW_HISTORY_KEY = "draw_history"

# Nombre de questions récentes qu'on évite de resservir, pour un même mode et
# les mêmes filtres. Un tirage purement indépendant à chaque partie fait
# revenir les mêmes questions bien avant d'avoir épuisé un lot de 50 ou 100 :
# on retient donc les dernières servies plutôt que de retirer au hasard dans
# tout le lot à chaque fois. La limite reste fixe (et non la taille du lot)
# pour que le cookie de session ne grossisse pas avec le catalogue.
DRAW_HISTORY_LIMIT = 60

def draw_run_questions(
    mode: str,
    tag_id: int | None = None,
    content_type: str | None = None,
    tag_ids: list[int] | None = None,
) -> list[int]:
    """Tire au sort les questions d'une nouvelle partie, en évitant de resservir
    une question vue récemment dans ce même mode et ces mêmes filtres

    Le tirage a lieu une seule fois, au lancement : deux parties du même mode
    ne se ressemblent pas, mais à l'intérieur d'une partie l'ordre ne bouge
    plus, sans quoi avancer d'une question en ramènerait une déjà posée"""
    pool_ids = [
        row.id for row in playable_question_query(mode, tag_id, content_type, tag_ids).all()
    ]
    target_size = min(QUESTIONS_PER_RUN, len(pool_ids))
    filters = run_filters(tag_id, content_type, tag_ids)

    history = session.get(DRAW_HISTORY_KEY)
    recent_ids = (
        history["ids"]
        if history and history["mode"] == mode and history["filters"] == filters
        else []
    )
    # Une question a pu disparaître du JSON depuis le dernier tirage.
    recent_ids = [qid for qid in recent_ids if qid in pool_ids]

    candidates = [qid for qid in pool_ids if qid not in recent_ids]
    if len(candidates) < target_size:
        # Pas assez d'inédit pour composer une partie complète : la mémoire
        # récente a fait le tour du lot, on la vide plutôt que d'imposer une
        # partie incomplète alors que des questions restent jouables.
        recent_ids = []
        candidates = pool_ids

    random.shuffle(candidates)
    drawn = candidates[:QUESTIONS_PER_RUN]

    session[DRAW_HISTORY_KEY] = {
        "mode": mode,
        "filters": filters,
        "ids": (recent_ids + drawn)[-DRAW_HISTORY_LIMIT:],
    }

    return drawn

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
