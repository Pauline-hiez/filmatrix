"""Définition des raretés de personnages et leur habillage visuel."""

RARITIES = {
    "commun": {
        "label": "Commun",
        "border_color": "border-slate-500",
        "glow_class": "",
        "text_color": "text-slate-400",
    },
    "rare": {
        "label": "Rare",
        "border_color": "border-emerald-400",
        "glow_class": "shadow-[0_0_10px_rgba(52,211,153,0.3)]",
        "text_color": "text-emerald-400",
    },
    "epique": {
        "label": "Épique",
        "border_color": "border-blue-400",
        "glow_class": "shadow-[0_0_10px_rgba(96,165,250,0.4)]",
        "text_color": "text-blue-400",
    },
    "legendaire": {
        "label": "Légendaire",
        "border_color": "border-violet-400",
        "glow_class": "shadow-[0_0_15px_rgba(167,139,250,0.5)]",
        "text_color": "text-violet-400",
    },
    "mythique": {
        "label": "Mythique",
        "border_color": "border-amber-400",
        "glow_class": "shadow-[0_0_20px_rgba(251,191,36,0.6)]",
        "text_color": "text-amber-400",
    },
}

"""Fonctions utilitaires de formatage d'affichage"""

# Nombre de fragments nécessaires pour débloquer un personnage, selon sa
# rareté. Source unique : le formulaire d'admin pré-remplit son champ à
# partir d'ici (JS) et le serveur retombe sur ces valeurs en l'absence de
# champ.
# Plafond à 9 : la grille puzzle fait 3×3, au-delà toutes les cases seraient
# révélées avant la fin du déblocage.
RARITY_FRAGMENT_COSTS = {
    "commun": 3,
    "rare": 5,
    "epique": 7,
    "legendaire": 8,
    "mythique": 9,
}


def fragments_for_rarity(rarity: str, fallback: int = 5) -> int:
    """Renvoie le nombre de fragments pour une rareté donnée.

    Une rareté inconnue (ou une base historique) retombe sur ``fallback``
    plutôt que de planter.
    """
    return RARITY_FRAGMENT_COSTS.get(rarity, fallback)

def humanize_tag_name(name: str) -> str:
    """Transforme un nom de slug en vrai nom: indiana-jones -> Indiana Jones"""
    if " " in name or any(char.isupper() for char in name):
        return name

    return name.replace("-", " ").title()