"""Logique métier des Jeux Spéciaux : barème de récompense de chaque jeu.

Volontairement déterministe (pas de tirage aléatoire caché sur le montant
des récompenses) : le joueur doit pouvoir anticiper ce qu'il obtient selon sa
performance, contrairement au tirage d'un fragment (aléatoire sur LEQUEL
personnage, jamais sur le fait d'en recevoir un ou non à un palier donné).
"""

import difflib
import re
import unicodedata

from filmatrix.services.badges import award_badge, has_badge
from filmatrix.services.collection import award_guaranteed_fragment
from filmatrix.services.shop import award_title, owns_title

# Badges et titres exclusifs aux Jeux Spéciaux (voir services/badges.py et
# services/shop.py) : accordés une seule fois, à la première partie parfaite
# de chaque jeu — un badge/titre distinct par jeu, pour que la collection
# reflète lequel a été maîtrisé.
CACHE_CINE_BADGE_CODE = "oeil_cinephile"
CACHE_CINE_TITLE_CODE = "chasseur_de_references"
SCENE_MYSTERE_BADGE_CODE = "devin_du_cinema"
SCENE_MYSTERE_TITLE_CODE = "maitre_du_mystere"

RARE_AND_ABOVE = ["rare", "epique", "legendaire", "mythique"]

# Libellé affiché pour chaque palier de performance — partagé entre le calcul
# des récompenses ci-dessous et l'écran de sélection des scènes/cas
# (templates/special_games/*_choisir.html), qui affiche le meilleur palier
# obtenu par le joueur sans avoir à redupliquer ce mapping.
TIER_LABELS = {
    "parfaite": "Performance parfaite",
    "excellente": "Excellente performance",
    "bonne": "Bonne performance",
    "moyenne": "Performance moyenne",
    "echec": "Partie terminée",
}

# Seuil de similarité (difflib.SequenceMatcher.ratio, 0-1) au-delà duquel une
# réponse tapée par le joueur est considérée correcte malgré une petite faute
# de frappe. Pas de dépendance externe (type python-Levenshtein) pour un
# besoin aussi ponctuel : difflib suffit sur des titres courts.
ANSWER_MATCH_THRESHOLD = 0.84


def _normalize_answer(text: str) -> str:
    """Normalise une réponse Scène Mystère avant comparaison : accents,
    casse et ponctuation ignorés, espaces multiples réduits. Permet à
    "Le Seigneur des Anneaux" et "le seigneur   des anneaux !" de matcher la
    même entrée admin."""
    decomposed = unicodedata.normalize("NFKD", text)
    without_accents = "".join(char for char in decomposed if not unicodedata.combining(char))
    alnum_only = re.sub(r"[^a-z0-9 ]", " ", without_accents.lower())
    return re.sub(r"\s+", " ", alnum_only).strip()


def answer_matches(guess: str, accepted_texts: list[str]) -> bool:
    """Compare la réponse libre d'un joueur aux textes acceptés d'une zone
    Scène Mystère, en tolérant les petites fautes de frappe."""
    normalized_guess = _normalize_answer(guess or "")
    if not normalized_guess:
        return False

    for accepted in accepted_texts:
        normalized_accepted = _normalize_answer(accepted or "")
        if not normalized_accepted:
            continue
        if normalized_guess == normalized_accepted:
            return True
        ratio = difflib.SequenceMatcher(None, normalized_guess, normalized_accepted).ratio()
        if ratio >= ANSWER_MATCH_THRESHOLD:
            return True

    return False


def _apply_tier(
    user, tier: str, tier_label: str, xp: int, coins: int, fragment_result, badge_code: str, title_code: str
) -> dict:
    """Crédite XP/pièces et, sur une performance parfaite, accorde le badge
    et le titre exclusifs du jeu (une seule fois par compte). Factorisé
    entre les jeux : seuls le barème et les codes badge/titre diffèrent."""
    user.total_xp += xp
    user.coins += coins

    badge_awarded = False
    title_awarded = False
    if tier == "parfaite":
        if not has_badge(user, badge_code):
            award_badge(user, badge_code)
            badge_awarded = True
        if not owns_title(user, title_code):
            award_title(user, title_code)
            title_awarded = True

    return {
        "tier": tier,
        "tier_label": tier_label,
        "xp": xp,
        "coins": coins,
        "fragment_result": fragment_result,
        "badge_awarded": badge_awarded,
        "title_awarded": title_awarded,
    }


def _resolve_ratio_based_rewards(
    user, found_count: int, total: int, mistakes: int, badge_code: str, title_code: str
) -> dict:
    """Barème par palier de performance, commun à Cache-Ciné et Scène
    Mystère : ratio de références correctement trouvées (found_count/total)
    et nombre d'erreurs déterminent le palier. Une petite récompense de
    consolation est toujours donnée, même à 0 référence trouvée (jamais de
    partie à vide, § 19 du cahier des charges initial)."""
    ratio = (found_count / total) if total else 0

    if ratio >= 1 and mistakes == 0:
        tier, xp, coins = "parfaite", 200, 100
        fragment_result = award_guaranteed_fragment(user, minimum_rarity=RARE_AND_ABOVE)
    elif ratio >= 0.8:
        tier, xp, coins = "excellente", 150, 75
        fragment_result = award_guaranteed_fragment(user)
    elif ratio >= 0.5:
        tier, xp, coins = "bonne", 80, 40
        fragment_result = award_guaranteed_fragment(user)
    elif ratio > 0:
        tier, xp, coins = "moyenne", 40, 20
        fragment_result = None
    else:
        tier, xp, coins = "echec", 15, 10
        fragment_result = None

    return _apply_tier(user, tier, TIER_LABELS[tier], xp, coins, fragment_result, badge_code, title_code)


def resolve_cache_cine_rewards(user, found_count: int, total: int, mistakes: int) -> dict:
    """Calcule et distribue la récompense de fin de partie Cache-Ciné."""
    return _resolve_ratio_based_rewards(
        user, found_count, total, mistakes, CACHE_CINE_BADGE_CODE, CACHE_CINE_TITLE_CODE
    )


def resolve_scene_mystere_rewards(user, found_count: int, total: int, mistakes: int) -> dict:
    """Calcule et distribue la récompense de fin de partie Scène Mystère.

    Même barème que Cache-Ciné (found_count = références dont la zone a été
    trouvée ET le nom de l'œuvre correctement deviné, sur les ~10 de
    l'image).
    """
    return _resolve_ratio_based_rewards(
        user, found_count, total, mistakes, SCENE_MYSTERE_BADGE_CODE, SCENE_MYSTERE_TITLE_CODE
    )
