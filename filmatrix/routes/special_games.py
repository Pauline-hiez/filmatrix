"""Jeux Spéciaux : hub et déroulé de Cache-Ciné et Scène Mystère.

Catégorie à part des modes classiques (filmatrix/game_modes.py), débloquée
par les Tickets d'Or (User.golden_tickets) plutôt que toujours accessible.
Une partie vit en session Flask, comme une partie de quiz classique
(services/score.py) : pas de table dédiée, le ticket consommé au lancement
suffit à limiter la fréquence de jeu.
"""

import random

from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

from filmatrix.extensions import db
from filmatrix.models import (
    CacheCineReference,
    CacheCineScene,
    MysteryCase,
    MysteryOption,
    MysteryZone,
)
from filmatrix.services.collection import fragment_result_payload
from filmatrix.services.special_games import resolve_cache_cine_rewards, resolve_scene_mystere_rewards
from filmatrix.special_games import SPECIAL_GAMES, SPECIAL_GAMES_BY_SLUG

bp = Blueprint("special_games", __name__)

RUN_SESSION_KEY = "cache_cine_run"
RESULT_SESSION_KEY = "cache_cine_result"
LAST_SCENE_SESSION_KEY = "cache_cine_last_scene_id"

# Petite pénalité de temps appliquée côté client à chaque clic dans le vide
# (voir static/js/cache_cine.js) : assez sensible pour décourager le clic au
# hasard, sans punir une partie autrement solide (§ 7 du cahier des charges).
MISS_PENALTY_SECONDS = 3

SM_RUN_SESSION_KEY = "scene_mystere_run"
SM_RESULT_SESSION_KEY = "scene_mystere_result"
SM_LAST_CASE_SESSION_KEY = "scene_mystere_last_case_id"


@bp.route("/jeux-speciaux")
@login_required
def hub() -> str:
    """Page d'accueil des Jeux Spéciaux : les tickets du joueur, les deux jeux."""
    active_scene_count = CacheCineScene.query.filter_by(is_active=True).count()
    active_case_count = MysteryCase.query.filter_by(is_active=True).count()
    return render_template(
        "special_games/hub.html",
        special_games=SPECIAL_GAMES,
        active_scene_count=active_scene_count,
        active_case_count=active_case_count,
    )


def _draw_random_active(model, last_id_session_key: str):
    """Tire une ligne active au hasard, en évitant si possible de répéter la
    toute dernière jouée par ce joueur. Partagé par Cache-Ciné
    (CacheCineScene) et Scène Mystère (MysteryCase)."""
    rows = model.query.filter_by(is_active=True).all()
    if not rows:
        return None

    last_id = session.get(last_id_session_key)
    candidates = [row for row in rows if row.id != last_id] if len(rows) > 1 else rows

    return random.choice(candidates or rows)


def _draw_scene() -> CacheCineScene | None:
    return _draw_random_active(CacheCineScene, LAST_SCENE_SESSION_KEY)


def _draw_case() -> MysteryCase | None:
    return _draw_random_active(MysteryCase, SM_LAST_CASE_SESSION_KEY)


@bp.route("/jeux-speciaux/cache-cine/commencer", methods=["POST"])
@login_required
def cache_cine_start():
    """Consomme un Ticket d'Or et lance une partie de Cache-Ciné."""
    game = SPECIAL_GAMES_BY_SLUG["cache-cine"]

    if current_user.golden_tickets < game["ticket_cost"]:
        flash("Aucun Ticket d'Or disponible. Accomplis des missions pour en obtenir.")
        return redirect(url_for("special_games.hub"))

    scene = _draw_scene()
    if scene is None:
        flash("Aucune scène Cache-Ciné n'est disponible pour le moment.")
        return redirect(url_for("special_games.hub"))

    # Le ticket est consommé tout de suite, au lancement — jamais remboursé
    # en cas d'abandon, comme pour un ticket de cinéma réel (§ 2 du cahier
    # des charges : il donne accès au contenu, jamais un avantage en partie).
    current_user.golden_tickets -= game["ticket_cost"]
    db.session.commit()

    session[RUN_SESSION_KEY] = {
        "scene_id": scene.id,
        "found_reference_ids": [],
        "mistakes": 0,
    }
    session[LAST_SCENE_SESSION_KEY] = scene.id

    return redirect(url_for("special_games.cache_cine_play"))


@bp.route("/jeux-speciaux/cache-cine/jouer")
@login_required
def cache_cine_play() -> str:
    """Affiche l'écran de jeu de la partie de Cache-Ciné en cours."""
    run = session.get(RUN_SESSION_KEY)
    if not run:
        flash("Aucune partie de Cache-Ciné en cours.")
        return redirect(url_for("special_games.hub"))

    scene = CacheCineScene.query.get(run["scene_id"])
    if scene is None:
        session.pop(RUN_SESSION_KEY, None)
        flash("Cette scène n'existe plus.")
        return redirect(url_for("special_games.hub"))

    references = (
        CacheCineReference.query.filter_by(scene_id=scene.id)
        .order_by(CacheCineReference.order_index)
        .all()
    )

    return render_template(
        "special_games/cache_cine_jouer.html",
        scene=scene,
        references=references,
        found_reference_ids=run["found_reference_ids"],
        miss_penalty_seconds=MISS_PENALTY_SECONDS,
    )


@bp.route("/jeux-speciaux/cache-cine/clic", methods=["POST"])
@login_required
def cache_cine_click():
    """Traite le clic du joueur sur (ou hors) une zone de la scène en cours.

    Le zone_id vient du bouton cliqué côté client (chaque zone est déjà
    rendue à sa position exacte par le serveur) : pas de calcul de
    coordonnées ni de tolérance de clic à gérer ici, juste une référence
    valide ou non.
    """
    run = session.get(RUN_SESSION_KEY)
    if not run:
        return jsonify({"error": "no_run"}), 400

    payload = request.get_json(silent=True) or {}
    try:
        reference_id = int(payload.get("reference_id"))
    except (TypeError, ValueError):
        reference_id = None

    reference = None
    if reference_id is not None:
        reference = CacheCineReference.query.filter_by(
            id=reference_id, scene_id=run["scene_id"]
        ).first()

    if reference is not None and reference.id not in run["found_reference_ids"]:
        run["found_reference_ids"].append(reference.id)
        session[RUN_SESSION_KEY] = run
        total = CacheCineReference.query.filter_by(scene_id=run["scene_id"]).count()
        return jsonify(
            {
                "correct": True,
                "reference_id": reference.id,
                "title": reference.title,
                "found_count": len(run["found_reference_ids"]),
                "total": total,
            }
        )

    run["mistakes"] += 1
    session[RUN_SESSION_KEY] = run
    return jsonify({"correct": False, "mistakes": run["mistakes"], "penalty_seconds": MISS_PENALTY_SECONDS})


@bp.route("/jeux-speciaux/cache-cine/terminer", methods=["POST"])
@login_required
def cache_cine_finish():
    """Clôture la partie en cours, distribue les récompenses selon la performance."""
    run = session.pop(RUN_SESSION_KEY, None)
    if not run:
        flash("Aucune partie de Cache-Ciné en cours.")
        return redirect(url_for("special_games.hub"))

    total = CacheCineReference.query.filter_by(scene_id=run["scene_id"]).count()
    found_count = len(run["found_reference_ids"])

    rewards = resolve_cache_cine_rewards(
        current_user, found_count=found_count, total=total, mistakes=run["mistakes"]
    )
    db.session.commit()

    # Les fragments gagnés hors quiz classique passent par le même payload
    # front que templates/quiz/termine.html : l'écran de résultat peut ainsi
    # réutiliser tel quel static/js/fragment_reveal.js (même overlay, même
    # animation de paquet cadeau) plutôt qu'un troisième système d'écran de
    # fin de partie.
    fragment_payload = fragment_result_payload(current_user, rewards["fragment_result"])

    session[RESULT_SESSION_KEY] = {
        "found_count": found_count,
        "total": total,
        "mistakes": run["mistakes"],
        "tier": rewards["tier"],
        "tier_label": rewards["tier_label"],
        "xp": rewards["xp"],
        "coins": rewards["coins"],
        "badge_awarded": rewards["badge_awarded"],
        "title_awarded": rewards["title_awarded"],
        "fragment": fragment_payload,
    }

    return redirect(url_for("special_games.cache_cine_result"))


@bp.route("/jeux-speciaux/cache-cine/resultat")
@login_required
def cache_cine_result() -> str:
    """Écran de fin de partie : score et récompenses gagnées."""
    result = session.pop(RESULT_SESSION_KEY, None)
    if not result:
        flash("Aucun résultat de partie à afficher.")
        return redirect(url_for("special_games.hub"))

    return render_template("special_games/cache_cine_resultat.html", result=result)


@bp.route("/jeux-speciaux/scene-mystere/commencer", methods=["POST"])
@login_required
def scene_mystere_start():
    """Consomme un Ticket d'Or et lance une partie de Scène Mystère."""
    game = SPECIAL_GAMES_BY_SLUG["scene-mystere"]

    if current_user.golden_tickets < game["ticket_cost"]:
        flash("Aucun Ticket d'Or disponible. Accomplis des missions pour en obtenir.")
        return redirect(url_for("special_games.hub"))

    case = _draw_case()
    if case is None:
        flash("Aucun cas Scène Mystère n'est disponible pour le moment.")
        return redirect(url_for("special_games.hub"))

    zone_ids = [
        zone.id
        for zone in MysteryZone.query.filter_by(case_id=case.id).order_by(MysteryZone.order_index).all()
    ]
    if not case.image_url or not zone_ids:
        flash("Ce cas Scène Mystère n'est pas encore prêt à être joué.")
        return redirect(url_for("special_games.hub"))

    current_user.golden_tickets -= game["ticket_cost"]
    db.session.commit()

    session[SM_RUN_SESSION_KEY] = {
        "case_id": case.id,
        "order": zone_ids,
        "current_index": 0,
        "found_zone_ids": [],
        "mistakes": 0,
        # Zone dont le clic vient d'être validé, en attente de la réponse au
        # QCM — None tant qu'aucune zone n'a encore été trouvée pour la
        # question en cours.
        "pending_zone_id": None,
    }
    session[SM_LAST_CASE_SESSION_KEY] = case.id

    return redirect(url_for("special_games.scene_mystere_play"))


@bp.route("/jeux-speciaux/scene-mystere/jouer")
@login_required
def scene_mystere_play() -> str:
    """Affiche l'écran de jeu de la partie de Scène Mystère en cours."""
    run = session.get(SM_RUN_SESSION_KEY)
    if not run:
        flash("Aucune partie de Scène Mystère en cours.")
        return redirect(url_for("special_games.hub"))

    case = MysteryCase.query.get(run["case_id"])
    if case is None:
        session.pop(SM_RUN_SESSION_KEY, None)
        flash("Ce cas n'existe plus.")
        return redirect(url_for("special_games.hub"))

    zones = MysteryZone.query.filter_by(case_id=case.id).order_by(MysteryZone.order_index).all()

    total = len(run["order"])
    current_index = run["current_index"]
    current_clue = None
    if current_index < total:
        current_zone_id = run["order"][current_index]
        current_zone = next((zone for zone in zones if zone.id == current_zone_id), None)
        current_clue = current_zone.clue_text if current_zone else None

    return render_template(
        "special_games/scene_mystere_jouer.html",
        case=case,
        zones=zones,
        found_zone_ids=run["found_zone_ids"],
        current_clue=current_clue,
        found_count=len(run["found_zone_ids"]),
        total=total,
    )


@bp.route("/jeux-speciaux/scene-mystere/clic", methods=["POST"])
@login_required
def scene_mystere_click():
    """Traite le clic du joueur sur une zone pour la question en cours.

    Bonne zone → mémorise la zone en attente de réponse et renvoie les
    options de son QCM. Mauvaise zone → petite pénalité, le joueur retente
    sur la même question (un mauvais clic ne met jamais fin à la partie).
    """
    run = session.get(SM_RUN_SESSION_KEY)
    if not run or run["current_index"] >= len(run["order"]):
        return jsonify({"error": "no_run"}), 400

    payload = request.get_json(silent=True) or {}
    try:
        zone_id = int(payload.get("zone_id"))
    except (TypeError, ValueError):
        zone_id = None

    target_zone_id = run["order"][run["current_index"]]

    if zone_id == target_zone_id:
        run["pending_zone_id"] = zone_id
        session[SM_RUN_SESSION_KEY] = run

        options = MysteryOption.query.filter_by(zone_id=zone_id).order_by(MysteryOption.order_index).all()
        shuffled_options = options[:]
        random.shuffle(shuffled_options)

        return jsonify(
            {
                "correct": True,
                "zone_id": zone_id,
                "options": [{"id": option.id, "label": option.label} for option in shuffled_options],
            }
        )

    run["mistakes"] += 1
    session[SM_RUN_SESSION_KEY] = run
    return jsonify({"correct": False, "mistakes": run["mistakes"], "penalty_seconds": MISS_PENALTY_SECONDS})


@bp.route("/jeux-speciaux/scene-mystere/repondre", methods=["POST"])
@login_required
def scene_mystere_answer():
    """Valide la réponse au QCM de la question en cours, puis avance à la
    suivante — bonne réponse ou non, pas de deuxième tentative sur un QCM."""
    run = session.get(SM_RUN_SESSION_KEY)
    if not run or not run.get("pending_zone_id"):
        return jsonify({"error": "no_pending_zone"}), 400

    payload = request.get_json(silent=True) or {}
    try:
        option_id = int(payload.get("option_id"))
    except (TypeError, ValueError):
        option_id = None

    pending_zone_id = run["pending_zone_id"]
    option = MysteryOption.query.filter_by(id=option_id, zone_id=pending_zone_id).first() if option_id else None
    answer_correct = bool(option and option.is_correct)
    correct_option = MysteryOption.query.filter_by(zone_id=pending_zone_id, is_correct=True).first()

    if answer_correct:
        run["found_zone_ids"].append(pending_zone_id)
    else:
        run["mistakes"] += 1

    run["pending_zone_id"] = None
    run["current_index"] += 1
    session[SM_RUN_SESSION_KEY] = run

    total = len(run["order"])
    done = run["current_index"] >= total
    next_clue = None
    if not done:
        next_zone = MysteryZone.query.get(run["order"][run["current_index"]])
        next_clue = next_zone.clue_text if next_zone else None

    return jsonify(
        {
            "correct": answer_correct,
            "correct_label": correct_option.label if correct_option else None,
            "done": done,
            "next_clue": next_clue,
            "found_count": len(run["found_zone_ids"]),
            "total": total,
        }
    )


@bp.route("/jeux-speciaux/scene-mystere/terminer", methods=["POST"])
@login_required
def scene_mystere_finish():
    """Clôture la partie en cours, distribue les récompenses selon la performance."""
    run = session.pop(SM_RUN_SESSION_KEY, None)
    if not run:
        flash("Aucune partie de Scène Mystère en cours.")
        return redirect(url_for("special_games.hub"))

    total = len(run["order"])
    found_count = len(run["found_zone_ids"])

    rewards = resolve_scene_mystere_rewards(
        current_user, found_count=found_count, total=total, mistakes=run["mistakes"]
    )
    db.session.commit()

    # Même payload front que Cache-Ciné (services/collection.py) : l'écran de
    # résultat réutilise tel quel static/js/fragment_reveal.js quand un
    # fragment est gagné.
    fragment_payload = fragment_result_payload(current_user, rewards["fragment_result"])

    session[SM_RESULT_SESSION_KEY] = {
        "found_count": found_count,
        "total": total,
        "mistakes": run["mistakes"],
        "tier": rewards["tier"],
        "tier_label": rewards["tier_label"],
        "xp": rewards["xp"],
        "coins": rewards["coins"],
        "badge_awarded": rewards["badge_awarded"],
        "title_awarded": rewards["title_awarded"],
        "fragment": fragment_payload,
    }

    return redirect(url_for("special_games.scene_mystere_result"))


@bp.route("/jeux-speciaux/scene-mystere/resultat")
@login_required
def scene_mystere_result() -> str:
    """Écran de fin de partie : score et récompenses gagnées."""
    result = session.pop(SM_RESULT_SESSION_KEY, None)
    if not result:
        flash("Aucun résultat de partie à afficher.")
        return redirect(url_for("special_games.hub"))

    return render_template("special_games/scene_mystere_resultat.html", result=result)
