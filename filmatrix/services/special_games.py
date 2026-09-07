"""Logique métier des Jeux Spéciaux : barème de récompense de Cache-Ciné.

Volontairement déterministe (pas de tirage aléatoire caché sur le montant
des récompenses) : le joueur doit pouvoir anticiper ce qu'il obtient selon sa
performance, contrairement au tirage d'un fragment (aléatoire sur LEQUEL
personnage, jamais sur le fait d'en recevoir un ou non à un palier donné).
"""

from filmatrix.services.badges import award_badge, has_badge
from filmatrix.services.collection import award_guaranteed_fragment
from filmatrix.services.shop import award_title, owns_title

# Badge et titre exclusifs aux Jeux Spéciaux (voir services/badges.py et
# services/shop.py) : accordés une seule fois, à la première partie parfaite.
PERFECT_BADGE_CODE = "oeil_cinephile"
PERFECT_TITLE_CODE = "chasseur_de_references"

RARE_AND_ABOVE = ["rare", "epique", "legendaire", "mythique"]


def resolve_cache_cine_rewards(user, found_count: int, total: int, mistakes: int) -> dict:
    """Calcule et distribue la récompense de fin de partie Cache-Ciné.

    Barème par palier de performance (found_count/total, § 17 du cahier des
    charges) : une petite récompense de consolation est toujours donnée,
    même à 0 référence trouvée (jamais de partie à vide, § 19).
    """
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

    user.total_xp += xp
    user.coins += coins

    badge_awarded = False
    title_awarded = False
    if tier == "parfaite":
        if not has_badge(user, PERFECT_BADGE_CODE):
            award_badge(user, PERFECT_BADGE_CODE)
            badge_awarded = True
        if not owns_title(user, PERFECT_TITLE_CODE):
            award_title(user, PERFECT_TITLE_CODE)
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
