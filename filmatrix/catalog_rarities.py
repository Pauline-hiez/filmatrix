"""Définition des raretés de personnages et leur habillage visuel."""

import re

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


# Cadre décoratif appliqué sur l'image de chaque personnage, selon sa rareté
# (static/images/cadres/). Source unique : la macro de rendu
# (character_frame.html) et la preview admin (JS) lisent ce mapping.
RARITY_FRAME_IMAGES = {
    "commun": "rarete0.png",
    "rare": "rarete1.png",
    "epique": "rarete2.png",
    "legendaire": "rarete3.png",
    "mythique": "rarete4.png",
}


def frame_image_for_rarity(rarity: str) -> str | None:
    """Renvoie le nom de fichier du cadre pour une rareté (None = sans cadre)."""
    return RARITY_FRAME_IMAGES.get(rarity)

# Sigles et particularités qui ne suivent pas la règle « capitaliser chaque
# mot » d'un slug (etats-unis, tom-hanks, coree-du-sud...). Source unique :
# scripts/humanize_tag_slugs.py (migration ponctuelle des données déjà en
# base) réutilise ces mêmes tables plutôt que de les dupliquer.
HUMANIZE_SPECIAL_WORDS = {
    "usa": "USA",
    "uk": "Royaume-Uni",
    "hbo": "HBO",
    "bbc": "BBC",
    "wwe": "WWE",
    "disney": "Disney",
}

# Recollages et accents usuels du catalogue (mots géographiques, temporels,
# traits d'union des pays) qu'une simple capitalisation mot à mot ne peut pas
# deviner à elle seule.
HUMANIZE_FIXES = {
    r"\bEtats Unis\b": "États-Unis",
    r"\bRoyaume Uni\b": "Royaume-Uni",
    r"\bNouvelle Zelande\b": "Nouvelle-Zélande",
    # La minuscule de "du" vient du passage particules ci-dessous, exécuté
    # avant ces correctifs : seule cette forme peut encore matcher ici.
    r"\bCoree du Sud\b": "Corée du Sud",
    r"\bScience Fiction\b": "Science-fiction",
    r"\bCinema General\b": "Cinéma général",
    r"\bAnnees\b": "Années",
    r"\bFunes\b": "Funès",
    r"\bGuillermo Del Toro\b": "Guillermo del Toro",
    r"\bM Night\b": "M. Night",
    # Idem : "de" y arrive déjà en minuscule via le passage particules, cette
    # entrée restaure l'exception (patronyme, pas une particule générique).
    r"\bRobert de Niro\b": "Robert De Niro",
}


def humanize_tag_name(name: str) -> str:
    """Transforme un nom de tag stocké en slug (etats-unis, tom-hanks,
    comedie) en un nom lisible (États-Unis, Tom Hanks, Comédie).

    Appelé au moment de l'affichage (pas seulement lors de l'import) : un tag
    resterait affiché en slug tant que sa valeur en base ne serait pas
    corrigée sinon — notamment sur un environnement où la migration
    ponctuelle (scripts/humanize_tag_slugs.py) n'a pas encore tourné, comme
    la base de production. Un nom qui contient déjà un espace ou une
    majuscule est renvoyé tel quel : c'est déjà un nom lisible saisi à la
    main, pas un slug d'import — le retoucher risquerait de le déformer.
    """
    if " " in name or any(char.isupper() for char in name):
        return name

    words = []
    for part in name.split("-"):
        if part in HUMANIZE_SPECIAL_WORDS:
            words.append(HUMANIZE_SPECIAL_WORDS[part])
        elif part.isdigit():
            words.append(part)
        else:
            words.append(part.capitalize())
    result = " ".join(words)

    # Particules en minuscule sauf en début de nom (déjà capitalisé) — avant
    # les correctifs ci-dessous, pas après : "Robert De Niro" y est une
    # exception volontaire (patronyme), que ce passage écraserait sinon en
    # "Robert de Niro" en tournant après lui.
    result = re.sub(r"(?<=\S)\s(De|Du|La|Le)\b", lambda m: " " + m.group(1).lower(), result)

    for pattern, replacement in HUMANIZE_FIXES.items():
        result = re.sub(pattern, replacement, result)

    return result