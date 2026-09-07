"""Jeux Spéciaux : hub et déroulé de Cache-Ciné.

Catégorie à part des modes classiques (filmatrix/game_modes.py), débloquée
par les Tickets d'Or (User.golden_tickets) plutôt que toujours accessible.
Une partie de Cache-Ciné vit en session Flask, comme une partie de quiz
classique (services/score.py) : pas de table dédiée, le ticket consommé au
lancement suffit à limiter la fréquence de jeu.
"""

import random

from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

from filmatrix.extensions import db
from filmatrix.models import CacheCineReference, CacheCineScene
from filmatrix.services.collection import fragment_result_payload
from filmatrix.services.special_games import resolve_cache_cine_rewards
from filmatrix.special_games import SPECIAL_GAMES, SPECIAL_GAMES_BY_SLUG

bp = Blueprint("special_games", __name__)

RUN_SESSION_KEY = "cache_cine_run"
RESULT_SESSION_KEY = "cache_cine_result"
LAST_SCENE_SESSION_KEY = "cache_cine_last_scene_id"

# Petite pénalité de temps appliquée côté client à chaque clic dans le vide
# (voir static/js/cache_cine.js) : assez sensible pour décourager le clic au
# hasard, sans punir une partie autrement solide (§ 7 du cahier des charges).
MISS_PENALTY_SECONDS = 3


@bp.route("/jeux-speciaux")
@login_required
def hub() -> str:
    """Page d'accueil des Jeux Spéciaux : les tickets du joueur, les deux jeux."""
    active_scene_count = CacheCineScene.query.filter_by(is_active=True).count()
    return render_template(
        "special_games/hub.html",
        special_games=SPECIAL_GAMES,
        active_scene_count=active_scene_count,
    )


def _draw_scene() -> CacheCineScene | None:
    """Tire une scène active au hasard, en évitant si possible de répéter la
    toute dernière jouée par ce joueur."""
    scenes = CacheCineScene.query.filter_by(is_active=True).all()
    if not scenes:
        return None

    last_scene_id = session.get(LAST_SCENE_SESSION_KEY)
    candidates = [scene for scene in scenes if scene.id != last_scene_id] if len(scenes) > 1 else scenes

    return random.choice(candidates or scenes)


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
