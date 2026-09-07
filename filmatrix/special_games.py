"""Catalogue des Jeux Spéciaux : nom, pitch, description et icône.

Catégorie à part des modes classiques (voir filmatrix/game_modes.py) :
débloquée par les Tickets d'Or plutôt que toujours accessible, jamais
mélangée à GAME_MODES ni affichée sur /modes. Cette liste est la seule
source pour le hub (templates/special_games/hub.html) et les routes de jeu
(filmatrix/routes/special_games.py).
"""

SPECIAL_GAMES = [
    {
        "slug": "cache-cine",
        "name": "Cache-Ciné",
        "icon": "🔎",
        "tagline": "Le cinéma est caché sous vos yeux.",
        "description": (
            "Explorez une illustration remplie de références "
            "cinématographiques. Retrouvez les films et séries cachés dans "
            "le décor."
        ),
        "ticket_cost": 1,
        "available": True,
    },
    {
        "slug": "scene-mystere",
        "name": "Scène Mystère",
        "icon": "🎬",
        "tagline": "Observez. Déduisez. Trouvez le film.",
        "description": (
            "Plusieurs scènes vous sont présentées. Analysez les indices et "
            "choisissez celle qui correspond à la bonne œuvre."
        ),
        "ticket_cost": 1,
        "available": True,
    },
]

SPECIAL_GAMES_BY_SLUG = {game["slug"]: game for game in SPECIAL_GAMES}
