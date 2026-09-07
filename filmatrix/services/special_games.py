"""Logique métier des Jeux Spéciaux : barème de récompense de chaque jeu.

Volontairement déterministe (pas de tirage aléatoire caché sur le montant
des récompenses) : le joueur doit pouvoir anticiper ce qu'il obtient selon sa
performance, contrairement au tirage d'un fragment (aléatoire sur LEQUEL
personnage, jamais sur le fait d'en recevoir un ou non à un palier donné).
"""

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
        tier, tier_label, xp, coins = "parfaite", "Performance parfaite", 200, 100
        fragment_result = award_guaranteed_fragment(user, minimum_rarity=RARE_AND_ABOVE)
    elif ratio >= 0.8:
        tier, tier_label, xp, coins = "excellente", "Excellente performance", 150, 75
        fragment_result = award_guaranteed_fragment(user)
    elif ratio >= 0.5:
        tier, tier_label, xp, coins = "bonne", "Bonne performance", 80, 40
        fragment_result = award_guaranteed_fragment(user)
    elif ratio > 0:
        tier, tier_label, xp, coins = "moyenne", "Performance moyenne", 40, 20
        fragment_result = None
    else:
        tier, tier_label, xp, coins = "echec", "Partie terminée", 15, 10
        fragment_result = None

    return _apply_tier(user, tier, tier_label, xp, coins, fragment_result, badge_code, title_code)


def resolve_cache_cine_rewards(user, found_count: int, total: int, mistakes: int) -> dict:
    """Calcule et distribue la récompense de fin de partie Cache-Ciné."""
    return _resolve_ratio_based_rewards(
        user, found_count, total, mistakes, CACHE_CINE_BADGE_CODE, CACHE_CINE_TITLE_CODE
    )


def resolve_scene_mystere_rewards(user, found_count: int, total: int, mistakes: int) -> dict:
    """Calcule et distribue la récompense de fin de partie Scène Mystère.

    Même barème que Cache-Ciné (found_count = références dont la zone ET le
    QCM ont été résolus correctement, sur les ~10 de l'image).
    """
    return _resolve_ratio_based_rewards(
        user, found_count, total, mistakes, SCENE_MYSTERE_BADGE_CODE, SCENE_MYSTERE_TITLE_CODE
    )
