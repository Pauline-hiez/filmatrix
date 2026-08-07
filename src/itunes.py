"""Fonctions d'accès à l'API iTunes Search pour récupérer les extraits audio"""

import requests 

ITUNES_SEARCH_URL = "https://itunes.apple.com/search"

def search_soundtrack_preview(search_term: str) -> str | None:
    """Recherche un extrait audio via l'API"""
    response = requests.get(
            ITUNES_SEARCH_URL,
            params={"term": search_term, "media": "music", "limit": 1},
        )
    data = response.json()

    results = data.get("results", [])
    if not results:
        return None

    return results[0].get("previewUrl")