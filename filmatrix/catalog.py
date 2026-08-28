"""Listes de référence affichées par l'interface.

Elles ne contiennent aucune logique : ce sont les valeurs que les gabarits et
les formulaires proposent au joueur. Les regrouper évite un module d'une
poignée de lignes par liste.
"""

# Galerie d'avatars proposée à l'inscription et sur l'édition de profil.
AVATARS = [
    "🎬", "🎭", "🍿", "🎥", "📽️", "🎞️",
    "👽", "🤖", "🦸", "🧙", "🕵️", "👻",
    "🐺", "🦁", "🐉", "🦈", "🦉", "🦊",
]

# Motifs proposés quand un joueur signale une question.
REPORT_REASON = {
    "wrong_answer": "La réponse indiquée comme correcte est fausse",
    "typo": "Faute de frappe ou d'orthographe",
    "broken_media": "Image ou audio cassé",
    "unclear": "Question ambiguë ou mal formulée",
    "other": "Autre",
}
