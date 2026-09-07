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

# Second chemin d'obtention d'un Ticket d'Or, en plus de la série de connexion
# de 7 jours (STREAK_BONUS_THRESHOLD, services/daily_challenges.py) : un
# ticket tous les N bonnes réponses cumulées, tous modes classiques confondus
# (voir routes/quiz.py). Récompense le volume de jeu plutôt que la régularité
# quotidienne — pensé pour les joueurs qui enchaînent des sessions plutôt que
# de jouer un peu chaque jour. 150 ≈ 15 parties (QUESTIONS_PER_RUN = 10,
# services/score.py) : largement atteignable en jouant régulièrement, sans
# inonder les joueurs très actifs de tickets en plus de ceux de la série.
CORRECT_ANSWERS_PER_TICKET = 150
