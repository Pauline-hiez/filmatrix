"""Suivi du score d'une partie solo, d'une question à l'autre.

Une partie n'a pas d'existence en base : elle vit dans la session du
navigateur, ce qui permet d'afficher un score de fin même à un visiteur non
connecté. Les fonctions prennent le magasin de session en argument plutôt que
d'aller le chercher elles-mêmes, pour rester testables avec un simple dict.
"""

SESSION_KEY = "run"

# Une partie solo tient en un nombre fixe de questions, choisi par le joueur
# sur l'écran de préparation parmi ces trois formats : le joueur sait dès le
# départ où il en est et quand cela s'arrête. Un mode qui en propose moins
# (filtre serré, catégorie peu fournie) fait forcément une partie plus courte.
QUESTIONS_PER_RUN = 10
RUN_LENGTH_PRESETS = {5: "Rapide", 10: "Classique", 20: "Challenge"}


def resolve_run_length(raw_value: str | int | None) -> int:
    """Valide la longueur de partie demandée, ou retombe sur le format par défaut

    Une valeur absente ou hors des formats proposés (lien trafiqué, ancien
    favori) ne doit pas planter la partie : elle retombe simplement sur
    QUESTIONS_PER_RUN, comme avant que ce choix n'existe."""
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return QUESTIONS_PER_RUN

    return value if value in RUN_LENGTH_PRESETS else QUESTIONS_PER_RUN


def start_run(store, mode: str, question_ids: list[int] | None = None, filters: dict | None = None) -> None:
    """Démarre le suivi d'une nouvelle partie, en écrasant la précédente

    Les questions tirées au sort sont retenues telles quelles : la partie doit
    garder le même ordre d'une question à l'autre, sinon le joueur retomberait
    sur des questions déjà vues en avançant. Les filtres qui ont servi au tirage
    sont retenus avec, pour ne pas resservir cette liste à une partie lancée
    avec d'autres réglages"""
    store[SESSION_KEY] = {
        "mode": mode,
        "correct": 0,
        "answered": [],
        "xp": 0,
        "coins": 0,
        "questions": question_ids or [],
        "filters": filters or {},
        "current_streak": 0,
        "fragment_awarded": False,
    }

def run_fragment_awarded(store, mode: str) -> bool:
    """Indique si un fragment a déjà été attribué pendant la partie en cours"""
    run = store.get(SESSION_KEY)
    return bool(run and run.get("mode") == mode and run.get("fragment_awarded", False))


def mark_run_fragment_awarded(store, mode: str) -> None:
    """Marque la partie en cours comme ayant déjà offert son fragment"""
    run = store.get(SESSION_KEY)
    if run is None or run.get("mode") != mode:
        return
    run["fragment_awarded"] = True
    store[SESSION_KEY] = run


def run_question_id(store, mode: str, position: int, filters: dict | None = None) -> int | None:
    """Retourne l'id de la question tirée pour cette position, ou None

    None veut dire qu'aucun tirage ne s'applique ici — partie d'un autre mode,
    réglages différents, session expirée ou lien direct — et que l'appelant doit
    retomber sur l'ordre stable des questions"""
    run = store.get(SESSION_KEY)

    if run is None or run["mode"] != mode:
        return None

    if run.get("filters", {}) != (filters or {}):
        return None

    questions = run.get("questions", [])

    if position < 1 or position > len(questions):
        return None

    return questions[position - 1]


def run_length(store, mode: str, filters: dict | None = None) -> int | None:
    """Retourne le nombre de questions tirées pour la partie en cours, ou None"""
    run = store.get(SESSION_KEY)

    if run is None or run["mode"] != mode or run.get("filters", {}) != (filters or {}):
        return None

    return len(run.get("questions", [])) or None


def record_answer(
    store, mode: str, question_id: int, is_correct: bool, xp: int = 0, coins: int = 0
) -> None:
    """Ajoute une réponse au score de la partie en cours

    Une même question n'est comptée qu'une fois : recharger la page pour
    répondre à nouveau ne doit pas gonfler le total"""
    run = store.get(SESSION_KEY)

    if run is None or run["mode"] != mode:
        start_run(store, mode)
        run = store[SESSION_KEY]

    if question_id in run["answered"]:
        return

    run["answered"].append(question_id)
    if is_correct:
        run["correct"] += 1
        run["current_streak"] = run.get("current_streak", 0) + 1
    else:
        run["current_streak"] = 0
    run["xp"] += xp
    run["coins"] += coins

    # Réaffectation nécessaire : la session Flask ne détecte pas la modification
    # d'un dictionnaire imbriqué, et ne renverrait pas le cookie mis à jour.
    store[SESSION_KEY] = run


def read_run(store, mode: str) -> dict | None:
    """Retourne le score de la partie terminée dans ce mode, ou None

    None signifie qu'il n'y a rien à afficher : partie d'un autre mode, ou
    joueur arrivé sur l'écran de fin sans avoir répondu à quoi que ce soit"""
    run = store.get(SESSION_KEY)

    if run is None or run["mode"] != mode or not run["answered"]:
        return None

    total = len(run["answered"])

    return {
        "correct": run["correct"],
        "total": total,
        "percentage": round(run["correct"] * 100 / total),
        "xp": run["xp"],
        "coins": run["coins"],
    }
