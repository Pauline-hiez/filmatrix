"""Listes de référence affichées par l'interface.

Elles ne contiennent aucune logique : ce sont les valeurs que les gabarits et
les formulaires proposent au joueur. Les regrouper évite un module d'une
poignée de lignes par liste.
"""

# Galerie d'avatars proposée à l'inscription et sur l'édition de profil.
# Chaque id correspond à une image dans static/images/avatars/<id>.png.
AVATARS = [str(number) for number in range(1, 20)]

# Utilisé pour les comptes créés avant cette galerie (avatar vide en base).
# Le même repli est câblé en dur dans templates/partials/avatar.html, qui ne
# peut pas importer de constante Python : à garder synchronisé si elle change.
DEFAULT_AVATAR = "1"

# Motifs proposés quand un joueur signale une question.
REPORT_REASON = {
    "wrong_answer": "La réponse indiquée comme correcte est fausse",
    "typo": "Faute de frappe ou d'orthographe",
    "broken_media": "Image ou audio cassé",
    "unclear": "Question ambiguë ou mal formulée",
    "other": "Autre",
}
