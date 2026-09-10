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

# Un visiteur non connecté peut tester n'importe quel mode, mais seulement sur
# ces quelques questions : de quoi se faire une idée du jeu sans pouvoir
# jouer une partie complète sans compte. Passé ce nombre, find_question()
# renvoie None comme en fin de partie normale, et termine.html prend le
# relais avec l'invitation à se connecter.
GUEST_PREVIEW_LENGTH = 3


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
        # Rien de ce qui est gagné pendant la partie n'est écrit en base au
        # fil de l'eau : ces listes accumulent ce qu'il faudra appliquer
        # d'un coup à la fin (filmatrix/services/run_rewards.py). Une partie
        # abandonnée ne les voit jamais consommées - start_run() écrase tout
        # à la partie suivante, ce qui suffit à tout annuler.
        "pending_attempts": [],
        "fragment_candidates": [],
        "fragment_results": [],
        "finalized": False,
        "reveal": None,
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


def add_run_fragment_result(store, mode: str, payload: dict) -> None:
    """Met de côté un gain de fragment pour l'écran de fin de partie.

    Les fragments ne sont révélés qu'à la fin d'une partie, jamais pendant
    (voir templates/quiz/termine.html) : plutôt que d'être renvoyés tout de
    suite au client, ils s'accumulent ici au fil des questions."""
    run = store.get(SESSION_KEY)
    if run is None or run.get("mode") != mode:
        return
    run.setdefault("fragment_results", []).append(payload)
    store[SESSION_KEY] = run


def read_run_fragment_results(store, mode: str) -> list[dict]:
    """Retourne les gains de fragments accumulés pendant la partie en cours."""
    run = store.get(SESSION_KEY)
    if run is None or run.get("mode") != mode:
        return []
    return run.get("fragment_results", [])


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
) -> bool:
    """Ajoute une réponse au score de la partie en cours

    Une même question n'est comptée qu'une fois : recharger la page pour
    répondre à nouveau ne doit pas gonfler le total. Retourne True si cet
    appel vient réellement d'enregistrer une nouvelle réponse (False pour un
    doublon), pour que l'appelant sache s'il doit mettre en file les
    récompenses de cette question (voir queue_pending_attempt) - sans quoi
    rejouer la même requête empilerait deux fois le même Attempt en attente."""
    run = store.get(SESSION_KEY)

    if run is None or run["mode"] != mode:
        start_run(store, mode)
        run = store[SESSION_KEY]

    if question_id in run["answered"]:
        return False

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
    return True


def queue_pending_attempt(
    store, mode: str, question_id: int, is_correct: bool, earned_xp: int, current_run_streak: int
) -> None:
    """Met en attente les données nécessaires pour créer l'Attempt de cette
    question, sans l'écrire en base tout de suite (voir run_rewards.py)"""
    run = store.get(SESSION_KEY)
    if run is None or run.get("mode") != mode:
        return
    run.setdefault("pending_attempts", []).append(
        {
            "question_id": question_id,
            "is_correct": is_correct,
            "earned_xp": earned_xp,
            "current_run_streak": current_run_streak,
        }
    )
    store[SESSION_KEY] = run


def queue_fragment_candidate(store, mode: str, question_id: int, character_name: str | None) -> None:
    """Met en attente une question éligible à un fragment personnel, sans le
    tirer tout de suite - un seul candidat aboutira, à la finalisation"""
    run = store.get(SESSION_KEY)
    if run is None or run.get("mode") != mode:
        return
    run.setdefault("fragment_candidates", []).append(
        {"question_id": question_id, "character_name": character_name}
    )
    store[SESSION_KEY] = run


def mark_run_finalized(store, mode: str) -> None:
    """Marque la partie en cours comme finalisée : ses récompenses ont été
    appliquées, un rechargement de l'écran de fin ne doit pas les recréditer"""
    run = store.get(SESSION_KEY)
    if run is None or run.get("mode") != mode:
        return
    run["finalized"] = True
    store[SESSION_KEY] = run


def is_run_finalized(store, mode: str) -> bool:
    """Indique si la partie en cours a déjà été finalisée"""
    run = store.get(SESSION_KEY)
    return bool(run and run.get("mode") == mode and run.get("finalized", False))


def read_run_reveal(store, mode: str) -> dict | None:
    """Retourne le résumé des récompenses de fin de partie (passage de
    niveau, badges, mini-missions, série) une fois la partie finalisée"""
    run = store.get(SESSION_KEY)
    if run is None or run.get("mode") != mode:
        return None
    return run.get("reveal")


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
