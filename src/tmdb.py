"""Fonctions d'accès à l'API TMDB"""

import os 
import requests

TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"

def get_api_key() -> str:
    """Récupère le clé API TMDB depuis .env"""
    return os.environ["TMDB_API_KEY"]

def search_movie(title: str) -> dict | None:
    """Recherche un film par son titre et renvoie ses informations principales.

    Renvoie None si aucun film n'est trouvé.
    """
    response = requests.get(
        f"{TMDB_BASE_URL}/search/movie",
        params={"api_key": get_api_key(), "query": title, "language": "fr-FR"},
    )
    data = response.json()

    results = data.get("results", [])
    if not results:
        return None

    movie = results[0]
    return {
        "id": movie["id"],
        "title": movie["title"],
        "poster_path": movie.get("poster_path"),
        "backdrop_path": movie.get("backdrop_path"),
    }

def get_movie_cast(movie_id: int, limit: int = 5) -> list[dict]:
    """Récupère les principaux acteurs d'un film, avec leur photo"""
    response = requests.get(
            f"{TMDB_BASE_URL}/movie/{movie_id}/credits",
            params={"api_key": get_api_key(), "language": "fr-FR"},
        )
    data = response.json()

    cast = data.get("cast", [])[:limit]
    return [
        {
            "name": actor["name"],
            "profile_path": actor.get("profile_path"),
            }
            for actor in cast
        ]

def build_image_url(image_path: str | None) -> str | None:
    """Construit l'url complète d'une image TMDB"""
    if not image_path:
        return None
    return f"{TMDB_IMAGE_BASE_URL}{image_path}"