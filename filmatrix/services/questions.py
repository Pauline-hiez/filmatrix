"""Sélection des questions d'une partie solo.

Ces fonctions vivaient dans create_app(), imbriquées dans la fabrique de
l'application : elles y étaient inaccessibles aux tests comme aux blueprints.
Elles ne dépendent que du modèle et de la session, leur place est ici.
"""

import random
import unicodedata

from flask import session
from flask_login import current_user
from sqlalchemy import func

from filmatrix.extensions import db
from filmatrix.game_modes import MIX_MODE_SLUG
from filmatrix.models import Character, Question, Tag, question_tags
from filmatrix.services.character_answers import CHARACTER_ANSWERS
from filmatrix.services.score import QUESTIONS_PER_RUN, run_question_id

# Ces modes donnent directement un indice de la réponse (image, casting,
# emojis, extrait audio ou lettres du titre). Avec un univers sélectionné,
# afficher leur question rend la réponse trop évidente : le Mix les exclut.
INCOMPATIBLE_MIX_MODES_FOR_UNIVERSE = {
    "devinette_affiche",
    "casting",
    "emoji",
    "blindtest",
    "film_melange",
}

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


def reachable_tag_ids(
    mode: str, content_type: str | None, selected_tag_ids: list[int]
) -> tuple[list[int], dict[str, list[int]]]:
    """Calcule, pour les filtres actifs, les tags qui garderaient au moins
    une question s'ils étaient ajoutés à la sélection

    Sans ça, un joueur peut choisir « Horreur » puis « Années 2000 » sans
    savoir qu'aucune question ne réunit les deux, et se retrouver devant un
    compteur à zéro qu'il ne comprend pas. Renvoie (défaut, par_type) :
    défaut sert à tout sélecteur qui n'a rien de choisi pour l'instant ;
    par_type ne couvre que les types de tag déjà représentés dans la
    sélection, en retirant leur propre tag du calcul — sans quoi un
    sélecteur ne proposerait plus jamais que sa valeur actuelle, deux genres
    différents ne cohabitant en général pas sur la même question."""

    def matching_tag_ids(excluding: int | None) -> set[int]:
        remaining = [tag_id for tag_id in selected_tag_ids if tag_id != excluding]
        question_ids = [
            row.id
            for row in playable_question_query(mode, content_type=content_type, tag_ids=remaining)
            .with_entities(Question.id)
            .all()
        ]
        if not question_ids:
            return set()

        rows = (
            db.session.query(question_tags.c.tag_id)
            .filter(question_tags.c.question_id.in_(question_ids))
            .distinct()
            .all()
        )
        return {row.tag_id for row in rows}

    default = matching_tag_ids(excluding=None)

    selected_types = (
        dict(db.session.query(Tag.id, Tag.tag_type).filter(Tag.id.in_(selected_tag_ids)).all())
        if selected_tag_ids
        else {}
    )

    by_type: dict[str, set[int]] = {}
    for tag_id, tag_type in selected_types.items():
        if tag_type not in by_type:
            by_type[tag_type] = matching_tag_ids(excluding=tag_id)

    return sorted(default), {tag_type: sorted(ids) for tag_type, ids in by_type.items()}


def reachable_content_types(mode: str, selected_tag_ids: list[int]) -> list[str]:
    """Types de contenu (film, série) qui garderaient au moins une question
    avec les tags actifs, sans contrainte de type de contenu — le pendant de
    reachable_tag_ids() pour le sélecteur Films / Séries."""
    rows = (
        playable_question_query(mode, tag_ids=selected_tag_ids)
        .with_entities(Question.content_type)
        .distinct()
        .all()
    )
    return sorted({row.content_type for row in rows})


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
    selected_tag_ids = tag_ids if tag_ids is not None else ([tag_id] if tag_id else [])

    has_universe_filter = bool(
        selected_tag_ids
        and Tag.query.filter(
            Tag.id.in_(selected_tag_ids), Tag.tag_type.in_(["univers", "saga"])
        ).first()
    )

    if mode == MIX_MODE_SLUG:
        query = Question.query
        if has_universe_filter:
            query = query.filter(~Question.mode.in_(INCOMPATIBLE_MIX_MODES_FOR_UNIVERSE))
            # Une citation sans attribution de personnage ne peut pas devenir
            # « Quel personnage a dit ça ? ». Elle est donc retirée du Mix,
            # tout comme les modes qui révèlent directement l'œuvre.
            query = query.filter(
                (Question.mode != "citation")
                | Question.id.in_(list(CHARACTER_ANSWERS))
                | Question.correct_answer["character"].as_string().isnot(None)
            )
    else:
        query = Question.query.filter_by(mode=mode)


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
    total_questions: int = QUESTIONS_PER_RUN,
) -> int:
    """Retourne le nombre de questions que comptera la partie

    Une partie fait total_questions questions (le joueur choisit parmi
    RUN_LENGTH_CHOICES sur l'écran de préparation), sauf si les filtres du
    joueur en laissent moins : on ne promet pas un total qu'on ne peut pas
    servir"""
    available = playable_question_query(mode, tag_id, content_type, tag_ids).count()
    return min(total_questions, available)

def run_filters(
    tag_id: int | None = None,
    content_type: str | None = None,
    tag_ids: list[int] | None = None,
    total_questions: int = QUESTIONS_PER_RUN,
) -> dict:
    """Décrit les réglages d'une partie, sous une forme rangeable en session

    total_questions y figure : une partie de 5 questions et une de 20 lancées
    avec les mêmes filtres ne doivent pas partager le même tirage en session."""
    normalized_tag_ids = tag_ids if tag_ids is not None else ([tag_id] if tag_id else [])
    return {"tag_ids": normalized_tag_ids, "content_type": content_type, "total_questions": total_questions}

DRAW_HISTORY_KEY = "draw_history"

# Nombre de questions récentes qu'on évite de resservir, pour un même mode et
# les mêmes filtres. Un tirage purement indépendant à chaque partie fait
# revenir les mêmes questions bien avant d'avoir épuisé un lot de 50 ou 100 :
# on retient donc les dernières servies plutôt que de retirer au hasard dans
# tout le lot à chaque fois. La limite reste fixe (et non la taille du lot)
# pour que le cookie de session ne grossisse pas avec le catalogue.
DRAW_HISTORY_LIMIT = 60


def _draw_history_key(mode: str, filters: dict) -> str:
    """Génère une clé unique d'historique pour un mode et ses filtres
    
    Chaque combinaison mode + filtres doit avoir son propre historique,
    sinon les historiques se écrasent mutuellement et les mêmes questions
    reviennent dans tous les modes.
    """
    # Crée une clé stable basée sur le mode et les filtres
    filters_key = str(sorted((k, str(v)) for k, v in filters.items()))
    return f"draw_history:{mode}:{filters_key}"


def draw_run_questions(
    mode: str,
    tag_id: int | None = None,
    content_type: str | None = None,
    tag_ids: list[int] | None = None,
    total_questions: int = QUESTIONS_PER_RUN,
) -> list[int]:
    """Tire au sort les questions d'une nouvelle partie, en évitant de resservir
    une question vue récemment dans ce même mode et ces mêmes filtres

    Le tirage a lieu une seule fois, au lancement : deux parties du même mode
    ne se ressemblent pas, mais à l'intérieur d'une partie l'ordre ne bouge
    plus, sans quoi avancer d'une question en ramènerait une déjà posée"""
    pool_ids = [
        row.id for row in playable_question_query(mode, tag_id, content_type, tag_ids).all()
    ]
    target_size = min(total_questions, len(pool_ids))
    filters = run_filters(tag_id, content_type, tag_ids, total_questions)

    # Utilise une clé unique pour ce mode et ces filtres
    history_key = _draw_history_key(mode, filters)
    recent_ids = session.get(history_key, [])
    
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
    drawn = candidates[:target_size]

    session[history_key] = (recent_ids + drawn)[-DRAW_HISTORY_LIMIT:]

    return drawn

def find_question(
    mode: str,
    position: int,
    tag_id: int | None = None,
    content_type: str | None = None,
    tag_ids: list[int] | None = None,
    total_questions: int = QUESTIONS_PER_RUN,
):
    """Cherche la question à une position donnée, parmi celles d'un mode, tag et type de contenu

    Renvoie None au-delà de la dernière position de la partie : c'est ce qui
    met fin à la partie et renvoie le joueur vers l'écran de score"""
    if position < 1 or position > total_questions:
        return None

    filters = run_filters(tag_id, content_type, tag_ids, total_questions)
    question_id = run_question_id(session, mode, position, filters)

    if question_id is not None:
        return Question.query.get(question_id)

    # Aucun tirage en session : lien direct vers une question, session
    # expirée ou navigation manuelle. On sert alors l'ordre stable par id,
    # plutôt que de refuser la question au joueur.
    query = build_question_query(mode, tag_id, content_type, tag_ids)

    return query.offset(position - 1).limit(1).first()

def _media_key(value: str) -> str:
    """Normalise un titre pour pouvoir retrouver son illustration."""
    decomposed = unicodedata.normalize("NFKD", value.lower())
    without_accents = "".join(
        char for char in decomposed if not unicodedata.combining(char)
    )
    return " ".join(
        "".join(char if char.isalnum() else " " for char in without_accents).split()
    )


def option_label(option) -> str:
    """Retourne le texte d'une option, qu'elle soit une chaîne ou un objet enrichi."""
    if isinstance(option, dict):
        return str(option.get("label") or option.get("text") or "")
    return str(option)


def option_image_url(question, option_index: int, option) -> str | None:
    """Résout l'image d'une option QCM sans rendre les images obligatoires.

    Priorité aux métadonnées ajoutées directement au QCM, puis aux affiches déjà
    présentes dans les questions `devinette_affiche` du même type de contenu.
    Les noms d'acteurs et de réalisateurs restent donc affichés en texte tant
    qu'aucun portrait n'est réellement fourni par les données.
    """
    payload = question.payload or {}
    explicit_images = payload.get("option_images")

    if isinstance(explicit_images, list) and option_index < len(explicit_images):
        image_url = explicit_images[option_index]
        if image_url:
            return image_url
    elif isinstance(explicit_images, dict):
        image_url = explicit_images.get(str(option_index)) or explicit_images.get(option_index)
        if image_url:
            return image_url

    if isinstance(option, dict) and option.get("image_url"):
        return option["image_url"]

    label = option_label(option).strip()
    if not label:
        return None

    # Un portrait de collection déjà enregistré peut illustrer directement un
    # choix de personnage. La recherche reste locale : aucun appel réseau ne doit
    # ralentir ou rendre aléatoire l'affichage d'une partie.
    character = Character.query.filter_by(name=label).first()
    if character and character.image_url:
        return character.image_url

    # Les affiches des modes image constituent le catalogue local d'illustrations
    # des œuvres. On ne fait jamais de recherche réseau pendant l'affichage d'une
    # question, et une réponse sans correspondance conserve son rendu texte.
    poster_questions = Question.query.filter_by(
        mode="devinette_affiche", content_type=question.content_type
    ).all()
    wanted_key = _media_key(label)
    for poster_question in poster_questions:
        answer = poster_question.correct_answer or {}
        title = answer.get("film") or answer.get("title")
        poster_url = (poster_question.payload or {}).get("poster_url")
        if title and poster_url and _media_key(title) == wanted_key:
            return poster_url

    return None


def shuffle_options(
    question, shuffler=None
) -> list[tuple[int, str, str | None]]:
    """Mélange les propositions d'un QCM avec leur index et leur image éventuelle.

    La bonne réponse est l'option 0 dans la majorité des questions : sans
    mélange, le joueur finit par répondre au réflexe. C'est bien l'index
    d'origine qui repart au serveur, la vérification reste donc inchangée.
    """
    options = [
        (index, option_label(option), option_image_url(question, index, option))
        for index, option in enumerate(question.payload["options"])
    ]
    (shuffler or random).shuffle(options)

    return options


def question_image_url(question) -> str | None:
    """Retourne l'affiche de contexte d'une question QCM uniquement.

    Les modes Casting et Devinette doivent conserver leurs propres indices et
    ne doivent jamais recevoir l'affiche de l'œuvre à deviner. L'URL enrichie
    est prioritaire. Pour une ancienne question sans champ
    d'image, on réutilise une affiche déjà enregistrée dans n'importe quel
    mode, lorsque le titre apparaît explicitement dans l'énoncé. Aucun appel
    réseau n'est effectué pendant le rendu d'une partie.
    """
    if question.mode != "qcm":
        return None

    payload = question.payload or {}
    direct_url = payload.get("question_image_url") or payload.get("poster_url")
    if direct_url:
        return direct_url

    prompt_key = _media_key(question.prompt or "")
    if prompt_key:
        # Le catalogue d'affiches ne se limite pas à devinette-affiche : les
        # enrichissements des citations, blind tests et devinettes peuvent aussi
        # servir de source à une ancienne question QCM.
        illustrated_questions = Question.query.filter_by(
            content_type=question.content_type
        ).all()
        candidates = []
        for illustrated_question in illustrated_questions:
            illustrated_payload = illustrated_question.payload or {}
            image_url = illustrated_payload.get("question_image_url") or illustrated_payload.get("poster_url")
            answer = illustrated_question.correct_answer or {}
            title = answer.get("film") or answer.get("title")
            if not title or not image_url:
                continue
            title_key = _media_key(title)
            if len(title_key) >= 4 and title_key in prompt_key:
                candidates.append((len(title_key), image_url))
        if candidates:
            return max(candidates, key=lambda candidate: candidate[0])[1]

    # Les modes qui ont déjà une œuvre comme réponse peuvent utiliser son
    # affiche, même lorsque le titre n'est pas répété dans l'énoncé.
    answer = question.correct_answer or {}
    title = answer.get("film") or answer.get("title")
    if title:
        wanted_key = _media_key(title)
        illustrated_questions = Question.query.filter_by(
            content_type=question.content_type
        ).all()
        for illustrated_question in illustrated_questions:
            illustrated_payload = illustrated_question.payload or {}
            image_url = illustrated_payload.get("question_image_url") or illustrated_payload.get("poster_url")
            illustrated_answer = illustrated_question.correct_answer or {}
            illustrated_title = illustrated_answer.get("film") or illustrated_answer.get("title")
            if (
                illustrated_title
                and image_url
                and _media_key(illustrated_title) == wanted_key
            ):
                return image_url

    return None


def content_label(question) -> str:
    """Retourne le libellé visible du type de contenu d'une question."""
    return "série" if question.content_type == "serie" else "film"


def content_title_phrase(question) -> str:
    """Retourne le complément correct pour parler du titre d'une œuvre."""
    return "de la série" if question.content_type == "serie" else "du film"


def content_question_phrase(question) -> str:
    """Retourne la formulation interrogative correcte pour une œuvre."""
    return "de quelle série" if question.content_type == "serie" else "de quel film"


def question_display_prompt(
    question,
    is_mix: bool = False,
    character_mode: bool = False,
) -> str:
    """Adapte les consignes du Mix au contenu réel de la question.

    Les fichiers de questions sont séparés entre films et séries, mais le Mix
    les rassemble. Une consigne enregistrée dans un ancien fichier peut donc
    conserver « film » alors que la question tirée est une série : l'interface
    doit toujours suivre le type réellement affiché.
    """
    if character_mode and question.mode == "citation":
        quote = question.prompt.split(" — ", 1)[0] if question.prompt else ""
        suffix = "Quel personnage a dit ça ?"
        return f"{quote} — {suffix}" if quote else suffix

    if not is_mix:
        return question.prompt

    label = content_label(question)
    if question.mode == "devinette":
        article = "Quel film" if label == "film" else "Quelle série"
        return f"{article} se cache derrière ces indices ?"

    if question.mode == "citation":
        quote = question.prompt.split(" — ", 1)[0] if question.prompt else ""
        suffix = f"{content_question_phrase(question).capitalize()} vient cette réplique ?"
        return f"{quote} — {suffix}" if quote else suffix

    return question.prompt


def answer_placeholder(
    question,
    is_mix: bool = False,
    character_mode: bool = False,
) -> str:
    """Retourne le placeholder adapté à la réponse attendue."""
    if character_mode and question.mode == "citation":
        return "Nom du personnage..."
    if is_mix and question.mode in {
        "citation", "devinette", "devinette_affiche", "casting", "blindtest",
    }:
        return f"Titre {content_title_phrase(question)}..."
    return "Titre du film..."


def format_correct_answer(question, alternate_answer: str | None = None) -> str:
    """Formate la bonne réponse, éventuellement adaptée au contexte de la partie."""
    if question.mode == "qcm":
        index = question.correct_answer["index"]
        return option_label(question.payload["options"][index])
    if question.mode == "vrai_faux":
        return  "Vrai" if question.correct_answer["value"] else "Faux"
    if question.mode == "chronologie":
        return "→".join(question.correct_answer["order"])
    if alternate_answer:
        return alternate_answer
    return question.correct_answer.get("film") or question.correct_answer.get("title") or ""
