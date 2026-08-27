"""Suivi du score d'une partie solo, d'une question à l'autre.

Une partie n'a pas d'existence en base : elle vit dans la session du
navigateur, ce qui permet d'afficher un score de fin même à un visiteur non
connecté. Les fonctions prennent le magasin de session en argument plutôt que
d'aller le chercher elles-mêmes, pour rester testables avec un simple dict.
"""

SESSION_KEY = "run"


def start_run(store, mode: str) -> None:
    """Démarre le suivi d'une nouvelle partie, en écrasant la précédente"""
    store[SESSION_KEY] = {
        "mode": mode,
        "correct": 0,
        "answered": [],
        "xp": 0,
        "coins": 0,
    }


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
