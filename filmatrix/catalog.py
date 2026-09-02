"""Listes de référence affichées par l'interface.

Elles ne contiennent aucune logique : ce sont les valeurs que les gabarits et
les formulaires proposent au joueur. Les regrouper évite un module d'une
poignée de lignes par liste.
"""

# Galerie d'avatars proposée à l'inscription et sur l'édition de profil.
# Chaque id correspond à une image dans static/images/avatars/<id>.png.
AVATARS = [str(number) for number in range(1, 20)]

# Couleur dominante de l'anneau propre à chaque image d'avatar (mesurée sur le
# fichier, jamais devinée) : sert à assortir la bordure d'un avatar affiché en
# grand (ex. profil) à l'anneau déjà dessiné dans l'image, plutôt qu'imposer
# une couleur fixe qui jurerait avec certains avatars.
AVATAR_RING_COLORS = {
    "1": "#02b0ef",
    "2": "#04a9ee",
    "3": "#01a9dd",
    "4": "#8a24e6",
    "5": "#8c24ea",
    "6": "#cf770c",
    "7": "#ec3552",
    "8": "#03b1e5",
    "9": "#f1be3c",
    "10": "#831eda",
    "11": "#0be5f5",
    "12": "#0379de",
    "13": "#08e2ec",
    "14": "#f23831",
    "15": "#ca0c15",
    "16": "#c946f9",
    "17": "#f5c231",
    "18": "#f3c03f",
    "19": "#04b6f8",
}

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
