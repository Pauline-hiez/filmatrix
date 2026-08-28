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

def search_movies_list(query: str, limit: int = 5) -> list[dict]:
    """Recherche plusieurs films correspondant à une requête, avec miniature"""
    if not query:
        return []

    response = requests.get(
        f"{TMDB_BASE_URL}/search/movie",
        params={"api_key": get_api_key(), "query": query, "language": "fr-FR"},
    )
    data = response.json()

    results = data.get("results", [])[:limit]
    return [
        {
            "id": movie["id"],
            "title": movie["title"],
            "year": movie["release_date"][:4] if movie.get("release_date") else "",
            "thumbnail_url": build_image_url(movie.get("poster_path")),
        }
        for movie in results
    ]

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

def get_movie_by_id(movie_id: int) -> dict | None:
    """Récupère les informations d'un film à partir de son id TMDB"""
    response = requests.get(
            f"{TMDB_BASE_URL}/movie/{movie_id}",
            params={"api_key": get_api_key(), "language": "fr-FR"},
        )
    if response.status_code != 200:
        return None

    movie = response.json()
    return {
        "id": movie["id"],
        "title": movie["title"],
        "poster_path": movie.get("poster_path"),
        "backdrop_path": movie.get("backdrop_path")
        }

def search_tv_show(title: str) -> dict | None:
    """Recherche une série par son titre et renvoie ses informations principales.

    Renvoie None si aucune série n'est trouvée.
    """
    response = requests.get(
        f"{TMDB_BASE_URL}/search/tv",
        params={"api_key": get_api_key(), "query": title, "language": "fr-FR"},
    )
    data = response.json()

    results = data.get("results", [])
    if not results:
        return None

    show = results[0]
    return {
        "id": show["id"],
        "title": show["name"],
        "poster_path": show.get("poster_path"),
        "backdrop_path": show.get("backdrop_path"),
    }


def get_tv_show_cast(tv_id: int, limit: int = 5) -> list[dict]:
    """Récupère les principaux acteurs d'une série, avec leur photo."""
    response = requests.get(
        f"{TMDB_BASE_URL}/tv/{tv_id}/credits",
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


def search_tv_shows_list(query: str, limit: int = 5) -> list[dict]:
    """Recherche plusieurs séries correspondant à une requête, avec miniature."""
    if not query:
        return []

    response = requests.get(
        f"{TMDB_BASE_URL}/search/tv",
        params={"api_key": get_api_key(), "query": query, "language": "fr-FR"},
    )
    data = response.json()

    results = data.get("results", [])[:limit]
    return [
        {
            "id": show["id"],
            "title": show["name"],
            "year": show["first_air_date"][:4] if show.get("first_air_date") else "",
            "thumbnail_url": build_image_url(show.get("poster_path")),
        }
        for show in results
    ]


def get_tv_show_by_id(tv_id: int) -> dict | None:
    """Récupère les informations d'une série à partir de son id TMDB."""
    response = requests.get(
        f"{TMDB_BASE_URL}/tv/{tv_id}",
        params={"api_key": get_api_key(), "language": "fr-FR"},
    )
    if response.status_code != 200:
        return None

    show = response.json()
    return {
        "id": show["id"],
        "title": show["name"],
        "poster_path": show.get("poster_path"),
        "backdrop_path": show.get("backdrop_path"),
    }