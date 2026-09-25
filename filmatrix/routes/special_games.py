"""Jeux Spéciaux : hub et déroulé de Cache-Ciné et Scène Mystère.

Catégorie à part des modes classiques (filmatrix/game_modes.py), débloquée
par les Tickets d'Or (User.golden_tickets) plutôt que toujours accessible.
Une partie vit en session Flask, comme une partie de quiz classique
(services/score.py) : pas de table dédiée pour la partie en cours, le ticket
consommé au lancement suffit à limiter la fréquence de jeu. Seul le meilleur
score par scène est persisté (CacheCineProgress / MysteryProgress), pour
l'écran de sélection.
"""

from datetime import datetime

from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

from filmatrix.extensions import db
from filmatrix.models import (
    CacheCineProgress,
    CacheCineReference,
    CacheCineScene,
    MysteryAnswer,
    MysteryCase,
    MysteryProgress,
    MysteryZone,
)
from filmatrix.services.collection import fragment_result_payload
from filmatrix.services.special_games import (
    TIER_LABELS,
    answer_matches,
    resolve_cache_cine_rewards,
    resolve_scene_mystere_rewards,
)
from filmatrix.special_games import SPECIAL_GAMES, SPECIAL_GAMES_BY_SLUG

bp = Blueprint("special_games", __name__)

RUN_SESSION_KEY = "cache_cine_run"
RESULT_SESSION_KEY = "cache_cine_result"

# Petite pénalité de temps appliquée côté client à chaque clic dans le vide
# (voir static/js/cache_cine.js) : assez sensible pour décourager le clic au
# hasard, sans punir une partie autrement solide (§ 7 du cahier des charges).
MISS_PENALTY_SECONDS = 3

SM_RUN_SESSION_KEY = "scene_mystere_run"
SM_RESULT_SESSION_KEY = "scene_mystere_result"


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


@bp.route("/jeux-speciaux/cache-cine/scenes")
@login_required
def cache_cine_choose() -> str:
    """Liste les scènes Cache-Ciné disponibles, avec le meilleur score du
    joueur sur chacune (templates/special_games/cache_cine_choisir.html) —
    remplace le tirage aléatoire précédent par un choix explicite."""
    game = SPECIAL_GAMES_BY_SLUG["cache-cine"]
    scenes = CacheCineScene.query.filter_by(is_active=True).order_by(CacheCineScene.created_at.desc()).all()
    reference_counts = {
        scene.id: CacheCineReference.query.filter_by(scene_id=scene.id).count() for scene in scenes
    }
    progress_by_scene_id = {
        progress.scene_id: progress
        for progress in CacheCineProgress.query.filter_by(user_id=current_user.id).all()
    }

    return render_template(
        "special_games/cache_cine_choisir.html",
        game=game,
        scenes=scenes,
        reference_counts=reference_counts,
        progress_by_scene_id=progress_by_scene_id,
        tier_labels=TIER_LABELS,
    )


@bp.route("/jeux-speciaux/cache-cine/commencer/<int:scene_id>", methods=["POST"])
@login_required
def cache_cine_start(scene_id: int):
    """Consomme un Ticket d'Or et lance une partie de Cache-Ciné sur la scène choisie."""
    game = SPECIAL_GAMES_BY_SLUG["cache-cine"]

    if current_user.golden_tickets < game["ticket_cost"]:
        flash("Aucun Ticket d'Or disponible. Accomplis des missions pour en obtenir.")
        return redirect(url_for("special_games.hub"))

    scene = CacheCineScene.query.filter_by(id=scene_id, is_active=True).first()
    if scene is None:
        flash("Cette scène Cache-Ciné n'est plus disponible.")
        return redirect(url_for("special_games.cache_cine_choose"))

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

    progress = CacheCineProgress.query.filter_by(user_id=current_user.id, scene_id=run["scene_id"]).first()
    if progress is None:
        progress = CacheCineProgress(
            user_id=current_user.id, scene_id=run["scene_id"], best_found_count=0, best_total=0,
            best_tier="echec", times_played=0,
        )
        db.session.add(progress)
    progress.times_played += 1
    progress.last_played_at = datetime.utcnow()
    if found_count > progress.best_found_count:
        progress.best_found_count = found_count
        progress.best_total = total
        progress.best_tier = rewards["tier"]

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


@bp.route("/jeux-speciaux/scene-mystere/cas")
@login_required
def scene_mystere_choose() -> str:
    """Liste les scènes Scène Mystère disponibles, avec le meilleur score du
    joueur sur chacune (templates/special_games/scene_mystere_choisir.html) —
    remplace le tirage aléatoire précédent par un choix explicite."""
    game = SPECIAL_GAMES_BY_SLUG["scene-mystere"]
    cases = MysteryCase.query.filter_by(is_active=True).order_by(MysteryCase.created_at.desc()).all()
    zone_counts = {case.id: MysteryZone.query.filter_by(case_id=case.id).count() for case in cases}
    progress_by_case_id = {
        progress.case_id: progress
        for progress in MysteryProgress.query.filter_by(user_id=current_user.id).all()
    }

    return render_template(
        "special_games/scene_mystere_choisir.html",
        game=game,
        cases=cases,
        zone_counts=zone_counts,
        progress_by_case_id=progress_by_case_id,
        tier_labels=TIER_LABELS,
    )


@bp.route("/jeux-speciaux/scene-mystere/commencer/<int:case_id>", methods=["POST"])
@login_required
def scene_mystere_start(case_id: int):
    """Consomme un Ticket d'Or et lance une partie de Scène Mystère sur la scène choisie."""
    game = SPECIAL_GAMES_BY_SLUG["scene-mystere"]

    if current_user.golden_tickets < game["ticket_cost"]:
        flash("Aucun Ticket d'Or disponible. Accomplis des missions pour en obtenir.")
        return redirect(url_for("special_games.hub"))

    case = MysteryCase.query.filter_by(id=case_id, is_active=True).first()
    if case is None:
        flash("Cette scène Scène Mystère n'est plus disponible.")
        return redirect(url_for("special_games.scene_mystere_choose"))

    zone_ids = [
        zone.id
        for zone in MysteryZone.query.filter_by(case_id=case.id).order_by(MysteryZone.order_index).all()
    ]
    if not case.image_url or not zone_ids:
        flash("Cette scène Scène Mystère n'est pas encore prête à être jouée.")
        return redirect(url_for("special_games.scene_mystere_choose"))

    current_user.golden_tickets -= game["ticket_cost"]
    db.session.commit()

    session[SM_RUN_SESSION_KEY] = {
        "case_id": case.id,
        # Aucun ordre imposé : chaque zone est une cible légitime dès le
        # départ (pas de décoy), le joueur clique celles qu'il repère dans
        # l'ordre qui lui plaît. zone_ids sert seulement à borner le total et
        # à vérifier qu'un zone_id cliqué appartient bien à cette scène.
        "zone_ids": zone_ids,
        # Zones déjà résolues (bonne ou mauvaise réponse tapée) : plus
        # cliquables, qu'elles aient été trouvées ou ratées.
        "attempted_zone_ids": [],
        "found_zone_ids": [],
        # Titres des œuvres déjà trouvées, dans l'ordre - avec doublons : une
        # même œuvre peut se cacher plusieurs fois dans une scène, cette
        # liste (affichée côté joueur) rend ça visible plutôt que de laisser
        # croire à un bug quand le même titre revient.
        "found_titles": [],
        "mistakes": 0,
        # Zone dont le clic vient d'être validé, en attente de la réponse
        # tapée par le joueur — None tant qu'aucune zone n'a encore été
        # trouvée pour la question en cours.
        "pending_zone_id": None,
    }

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
        flash("Cette scène n'existe plus.")
        return redirect(url_for("special_games.hub"))

    zones = MysteryZone.query.filter_by(case_id=case.id).order_by(MysteryZone.order_index).all()

    return render_template(
        "special_games/scene_mystere_jouer.html",
        case=case,
        zones=zones,
        # Union des zones trouvées et ratées : les deux ne sont plus
        # cliquables (une zone ne se tente qu'une fois), contrairement à
        # found_count (le score affiché) qui ne compte que les vraies trouvailles.
        resolved_zone_ids=run["attempted_zone_ids"],
        found_count=len(run["found_zone_ids"]),
        found_titles=run.get("found_titles", []),
        total=len(run["zone_ids"]),
    )


@bp.route("/jeux-speciaux/scene-mystere/clic", methods=["POST"])
@login_required
def scene_mystere_click():
    """Traite le clic du joueur sur une zone de son choix, dans l'ordre qu'il
    veut : il n'y a pas de décoy, chaque zone pas encore résolue est une
    cible légitime.

    Zone valide et pas encore résolue → mémorise la zone en attente de
    réponse ; le joueur passe ensuite au champ de réponse libre côté client.
    Sinon (zone déjà résolue, ou id inconnu) → petite pénalité, la partie
    continue (un clic invalide ne met jamais fin à la partie).
    """
    run = session.get(SM_RUN_SESSION_KEY)
    if not run or len(run["attempted_zone_ids"]) >= len(run["zone_ids"]):
        return jsonify({"error": "no_run"}), 400

    payload = request.get_json(silent=True) or {}
    try:
        zone_id = int(payload.get("zone_id"))
    except (TypeError, ValueError):
        zone_id = None

    is_valid_target = zone_id in run["zone_ids"] and zone_id not in run["attempted_zone_ids"]

    if is_valid_target:
        run["pending_zone_id"] = zone_id
        session[SM_RUN_SESSION_KEY] = run

        return jsonify({"correct": True, "zone_id": zone_id})

    run["mistakes"] += 1
    session[SM_RUN_SESSION_KEY] = run
    return jsonify({"correct": False, "mistakes": run["mistakes"], "penalty_seconds": MISS_PENALTY_SECONDS})


@bp.route("/jeux-speciaux/scene-mystere/repondre", methods=["POST"])
@login_required
def scene_mystere_answer():
    """Valide la réponse libre tapée par le joueur pour la zone en attente —
    bonne réponse ou non, pas de deuxième tentative sur une même zone, mais
    les autres zones restent disponibles dans l'ordre voulu par le joueur."""
    run = session.get(SM_RUN_SESSION_KEY)
    if not run or not run.get("pending_zone_id"):
        return jsonify({"error": "no_pending_zone"}), 400

    payload = request.get_json(silent=True) or {}
    guess = (payload.get("guess") or "").strip()

    pending_zone_id = run["pending_zone_id"]
    accepted_answers = (
        MysteryAnswer.query.filter_by(zone_id=pending_zone_id).order_by(MysteryAnswer.order_index).all()
    )
    answer_correct = answer_matches(guess, [answer.text for answer in accepted_answers])

    canonical_label = accepted_answers[0].text if accepted_answers else None

    run["attempted_zone_ids"].append(pending_zone_id)
    if answer_correct:
        run["found_zone_ids"].append(pending_zone_id)
        run.setdefault("found_titles", []).append(canonical_label or guess)
    else:
        run["mistakes"] += 1

    run["pending_zone_id"] = None
    session[SM_RUN_SESSION_KEY] = run

    total = len(run["zone_ids"])
    done = len(run["attempted_zone_ids"]) >= total

    return jsonify(
        {
            "correct": answer_correct,
            "correct_label": canonical_label,
            "done": done,
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

    total = len(run["zone_ids"])
    found_count = len(run["found_zone_ids"])

    rewards = resolve_scene_mystere_rewards(
        current_user, found_count=found_count, total=total, mistakes=run["mistakes"]
    )

    progress = MysteryProgress.query.filter_by(user_id=current_user.id, case_id=run["case_id"]).first()
    if progress is None:
        progress = MysteryProgress(
            user_id=current_user.id, case_id=run["case_id"], best_found_count=0, best_total=0,
            best_tier="echec", times_played=0,
        )
        db.session.add(progress)
    progress.times_played += 1
    progress.last_played_at = datetime.utcnow()
    if found_count > progress.best_found_count:
        progress.best_found_count = found_count
        progress.best_total = total
        progress.best_tier = rewards["tier"]

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
