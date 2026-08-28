"""Catalogue des modes de jeu : nom, pitch, règle, icône et couleur."""

# Métadonnées d'affichage des modes solo : nom, pitch et règle du jeu.
# Cette liste est la seule source : l'accueil, la page des modes et l'écran de
# préparation la lisent tous, pour ne pas décrire le même jeu de trois façons.
# "how" répond à la question que se pose un joueur qui découvre le mode : que
# vais-je voir à l'écran, et qu'attend-on de moi ?
GAME_MODES = [
    {
        "slug": "qcm",
        "name": "Quiz",
        "description": "Réponds à des questions sur tes films préférés.",
        "how": "Une question, quatre propositions. Une seule est la bonne, et leur ordre change à chaque partie.",
        "icon": "?",
        "accent": "#22d3ee",
    },
    {
        "slug": "blindtest",
        "name": "Blind Test",
        "description": "Reconnais les musiques de films cultes.",
        "how": "Un extrait de bande originale se lance. Tape le titre du film ou de la série qu'il accompagne.",
        "icon": "♪",
        "accent": "#60a5fa",
    },
    {
        "slug": "devinette_affiche",
        "name": "Devine le film",
        "description": "Une image, un film à trouver !",
        "how": "Une image tirée du tournage s'affiche, sans le titre. À toi de reconnaître l'œuvre et de l'écrire.",
        "icon": "▶",
        "accent": "#34d399",
    },
    {
        "slug": "citation",
        "name": "Citations",
        "description": "Retrouve le film grâce à une réplique.",
        "how": "Une réplique restée célèbre s'affiche. Retrouve l'œuvre d'où elle sort.",
        "icon": "❝",
        "accent": "#fbbf24",
    },
    {
        "slug": "casting",
        "name": "Acteurs",
        "description": "Reconnais les acteurs célèbres du cinéma.",
        "how": "Trois visages du casting principal, sans leur nom. Trouve ce qu'ils ont tourné ensemble.",
        "icon": "★",
        "accent": "#f472b6",
    },
    {
        "slug": "emoji",
        "name": "Emoji Quiz",
        "description": "Devine le film à partir des emojis.",
        "how": "Une poignée d'emojis raconte l'intrigue à leur manière. Décode-les et donne le titre.",
        "icon": "☺",
        "accent": "#c084fc",
    },
    {
        "slug": "film_melange",
        "name": "Film mélangé",
        "description": "Retrouve le titre à partir des lettres mélangées.",
        "how": "Les lettres du titre sont dans le désordre, les espaces à leur place. Remets-les dans l'ordre.",
        "icon": "⤭",
        "accent": "#a78bfa",
    },
    {
        "slug": "chronologie",
        "name": "Chronologie",
        "description": "Remets les films dans leur ordre de sortie.",
        "how": "Plusieurs titres s'affichent. Clique dessus du plus ancien au plus récent, puis valide.",
        "icon": "⏱",
        "accent": "#38bdf8",
    },
    {
        "slug": "devinette",
        "name": "Devinette",
        "description": "Devine le film grâce à des indices progressifs.",
        "how": "Un premier indice, puis un autre à chaque erreur. Plus tu trouves tôt, plus c'est fort.",
        "icon": "◎",
        "accent": "#fb923c",
    },
    {
        "slug": "vrai_faux",
        "name": "Vrai / Faux",
        "description": "Vraies ou fausses, à toi de trancher.",
        "how": "Une affirmation sur le cinéma s'affiche. Un seul geste : vrai, ou faux.",
        "icon": "±",
        "accent": "#2dd4bf",
    },
]

# Les modes ouverts au multijoueur. Ils le sont tous, mais la liste reste
# explicite : un mode dont l'écran de duel ne saurait pas afficher le média ou
# recueillir la réponse doit pouvoir en être retiré sans toucher au reste.
MULTIPLAYER_MODES = [entry["slug"] for entry in GAME_MODES]
