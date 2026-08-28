"""Définition des titres achetables de la boutique"""

from filmatrix.models import UserTitle 

TITLES = {
    "cinephile": {
        "name": "🎬 Cinéphile",
        "price": 50,
    },
    "horror_master": {
        "name": "🎃 Maître du cinéma d'horreur",
        "price": 100,
    },
    "quiz_legend": {
        "name": "👑 Légende du quiz",
        "price": 200,
    },
}

def owns_title(user, title_code: str) -> bool:
    """Vérifie si un utilisateur possède déjà un titre donné"""
    return any(title.title_code == title_code for title in user.titles)

def purchase_title(user, title_code: str) -> bool:
    """Achète un titre pour un utilisateur, si possible"""
    if title_code not in TITLES:
        return False

    if owns_title(user, title_code):
        return False

    price = TITLES[title_code]["price"]
    if user.coins < price:
        return False

    user.coins -= price
    new_title = UserTitle(title_code=title_code)
    user.titles.append(new_title)

    return True