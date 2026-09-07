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
    # Récompense des Jeux Spéciaux (filmatrix/services/special_games.py) :
    # price=None signale un titre jamais en vente, uniquement gagné en jeu —
    # routes/shop.py exclut ces entrées de la liste achetable.
    "chasseur_de_references": {
        "name": "🏷️ Chasseur de Références",
        "price": None,
        "exclusive": True,
    },
    "maitre_du_mystere": {
        "name": "🎭 Maître du Mystère",
        "price": None,
        "exclusive": True,
    },
}

def owns_title(user, title_code: str) -> bool:
    """Vérifie si un utilisateur possède déjà un titre donné"""
    return any(title.title_code == title_code for title in user.titles)

def purchase_title(user, title_code: str) -> bool:
    """Achète un titre pour un utilisateur, si possible"""
    if title_code not in TITLES:
        return False

    price = TITLES[title_code]["price"]
    if price is None:
        # Titre exclusif (voir award_title) : jamais achetable avec des pièces.
        return False

    if owns_title(user, title_code):
        return False

    if user.coins < price:
        return False

    user.coins -= price
    new_title = UserTitle(title_code=title_code)
    user.titles.append(new_title)

    return True

def award_title(user, title_code: str) -> bool:
    """Donne gratuitement un titre à un utilisateur (récompense de jeu plutôt
    qu'achat), s'il ne l'a pas déjà. Renvoie True si le titre vient d'être
    accordé."""
    if title_code not in TITLES:
        return False

    if owns_title(user, title_code):
        return False

    new_title = UserTitle(title_code=title_code)
    user.titles.append(new_title)

    return True