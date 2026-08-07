"""Script utilitaire : génère le JSON d'une question image à partir d'un titre de film"""

import json
import sys

from dotenv import load_dotenv

from src.tmdb import build_image_url, get_movie_cast, search_movie

load_dotenv()

def generate_poster_question(movie_title: str, difficulty: str, category: str) -> dict:
    """Génère le JSON d'une question Devinette-affiche pour un film donné"""
    movie = search_movie(movie_title)
    if movie is None:
        raise ValueError(f"Film introuvable sur TMDB : {movie_title}")

    poster_url = build_image_url(movie["poster_path"])

    return {
        "mode": "devinette_affiche",
        "category": category,
        "difficulty": difficulty,
        "prompt": "",
        "payload": {
                "poster_url": poster_url,
                "hints": [f"Ce film commence par la lettre {movie['title'][0]}."],
            },
        "correct_answer": {"film": movie["title"]},

        "requires_account": False,
        }

def generate_casting_question(movie_title: str, difficulty: str, category: str) -> dict:
    """Génère le JSON d'une question casting pour un film donné"""
    movie = search_movie(movie_title)
    if movie is None:
        raise ValueError(f"Film introuvable sur TMDB : {movie_title}")

    cast = get_movie_cast(movie["id"], limit=3)
    actor_photos = [
            build_image_url(actor["profile_path"]) for actor in cast if actor["profile_path"]
        ]

    return {
        "mode": "casting",
        "category": category,
        "difficulty": difficulty,
        "prompt": "",
        "payload": {"actor_photos": actor_photos},
        "correct_answer": {"film": movie["title"]},
        "requires_account": False,
        }

if __name__ == "__main__":
    mode = sys.argv[1]
    title = sys.argv[2]
    difficulty = sys.argv[3] if len(sys.argv) > 3 else "moyen"
    category = sys.argv[4] if len(sys.argv) > 4 else "anecdote"

    if mode == "affiche":
        question = generate_poster_question(title, difficulty, category)
    elif mode == "casting":
        question = generate_casting_question(title, difficulty, category)
    else:
        raise ValueError("Mode inconnu, utilise 'affiche' ou 'casting")

    print(json.dumps(question, indent=2, ensure_ascii=False))