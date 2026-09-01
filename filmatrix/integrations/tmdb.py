"""Fonctions d'accès à l'API TMDB"""

import os 
import requests

TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"

def get_api_key() -> str:
    """Récupère le clé API TMDB depuis .env"""
    return os.environ["TMDB_API_KEY"]

def search_movie(title: str, year: str | None = None) -> dict | None:
    """Recherche un film par son titre et renvoie ses informations principales.

    Le paramètre year lève l'ambiguïté des remakes et suites partageant le même
    titre (Alien, Blade Runner...). Renvoie None si aucun film n'est trouvé.
    """
    params = {"api_key": get_api_key(), "query": title, "language": "fr-FR"}
    if year:
        params["year"] = year
    response = requests.get(f"{TMDB_BASE_URL}/search/movie", params=params)
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
        "genre_ids": movie.get("genre_ids", []),
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

def search_people_list(query: str, limit: int = 5) -> list[dict]:
    """Recherche plusieurs personnes sur TMDB, avec leur portrait."""
    if not query:
        return []

    response = requests.get(
        f"{TMDB_BASE_URL}/search/person",
        params={"api_key": get_api_key(), "query": query, "language": "fr-FR"},
    )
    data = response.json()

    results = data.get("results", [])[:limit]
    return [
        {
            "name": person["name"],
            "profile_url": build_image_url(person.get("profile_path")),
            "known_for_department": person.get("known_for_department"),
        }
        for person in results
    ]


def get_movie_cast(movie_id: int, limit: int = 10) -> list[dict]:
    """Récupère les principaux acteurs d'un film, avec leur photo et le personnage joué"""
    response = requests.get(
            f"{TMDB_BASE_URL}/movie/{movie_id}/credits",
            params={"api_key": get_api_key(), "language": "fr-FR"},
        )
    data = response.json()

    cast = data.get("cast", [])[:limit]
    return [
        {
            "name": actor["name"],
            "character": actor.get("character"),
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

def search_tv_show(title: str, year: str | None = None) -> dict | None:
    """Recherche une série par son titre et renvoie ses informations principales.

    Le paramètre year lève l'ambiguïté des séries partageant le même titre.
    Renvoie None si aucune série n'est trouvée.
    """
    params = {"api_key": get_api_key(), "query": title, "language": "fr-FR"}
    if year:
        params["first_air_date_year"] = year
    response = requests.get(f"{TMDB_BASE_URL}/search/tv", params=params)
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
        "genre_ids": show.get("genre_ids", []),
    }


def get_tv_show_cast(tv_id: int, limit: int = 10) -> list[dict]:
    """Récupère les principaux acteurs d'une série, avec leur photo et le personnage joué"""
    response = requests.get(
        f"{TMDB_BASE_URL}/tv/{tv_id}/credits",
        params={"api_key": get_api_key(), "language": "fr-FR"},
    )
    data = response.json()

    cast = data.get("cast", [])[:limit]
    return [
        {
            "name": actor["name"],
            "character": actor.get("character"),
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


# Une œuvre a en général plusieurs genres TMDB à la fois (ex: Alien est à la
# fois science-fiction et horreur) : chacun devient son propre tag "genre",
# le modèle de données le permet déjà (relation many-to-many Question <-> Tag).
# Les genres sans intérêt pour un quiz de fiction (documentaire, téléfilm,
# talk-show...) ne sont volontairement pas repris.
GENRE_NAME_TO_TAGS: dict[str, list[str]] = {
    "Action": ["action"],
    "Action & Adventure": ["action", "aventure"],
    "Animation": ["animation"],
    "Aventure": ["aventure"],
    "Comédie": ["comédie"],
    "Crime": ["policier"],
    "Drame": ["drame"],
    "Enfants": ["familial"],
    "Familial": ["familial"],
    "Fantastique": ["fantasy"],
    "Guerre": ["guerre"],
    "Guerre & Politique": ["guerre"],
    "Histoire": ["histoire"],
    "Horreur": ["horreur"],
    "Musique": ["musique"],
    "Mystère": ["mystère"],
    "Romance": ["romance"],
    "Science-Fiction": ["science-fiction"],
    "Science-Fiction & Fantastique": ["science-fiction", "fantasy"],
    "Thriller": ["thriller"],
    "Western": ["western"],
}


def get_genre_maps() -> tuple[dict[int, str], dict[int, str]]:
    """Récupère les tables id -> nom des genres TMDB, pour films et séries

    Les résultats de recherche ne renvoient que des `genre_ids` : cette table
    est ce qui permet de les retraduire en noms de genre exploitables."""
    movie_response = requests.get(
        f"{TMDB_BASE_URL}/genre/movie/list",
        params={"api_key": get_api_key(), "language": "fr-FR"},
    )
    tv_response = requests.get(
        f"{TMDB_BASE_URL}/genre/tv/list",
        params={"api_key": get_api_key(), "language": "fr-FR"},
    )
    movie_genres = {genre["id"]: genre["name"] for genre in movie_response.json()["genres"]}
    tv_genres = {genre["id"]: genre["name"] for genre in tv_response.json()["genres"]}
    return movie_genres, tv_genres


def genre_ids_to_tags(genre_ids: list[int], genre_map: dict[int, str]) -> list[str]:
    """Traduit une liste de genre_ids TMDB en noms de tags internes, sans doublon"""
    tags: list[str] = []
    for genre_id in genre_ids:
        name = genre_map.get(genre_id)
        for tag in GENRE_NAME_TO_TAGS.get(name, []):
            if tag not in tags:
                tags.append(tag)
    return tags