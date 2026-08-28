"""Script utilitaire : génère le JSON d'une question image à partir d'un titre de film ou de série"""

import json
import sys

from dotenv import load_dotenv

from filmatrix.integrations.tmdb import (
    build_image_url,
    get_movie_cast,
    get_tv_show_cast,
    search_movie,
    search_tv_show,
)

load_dotenv()


def generate_poster_question(
    title: str, difficulty: str, category: str, content_type: str = "film"
) -> dict:
    """Génère le JSON d'une question Devinette-affiche pour un film ou une série donné"""
    result = search_tv_show(title) if content_type == "serie" else search_movie(title)
    if result is None:
        raise ValueError(f"Introuvable sur TMDB : {title}")

    poster_url = build_image_url(result["backdrop_path"])

    return {
        "mode": "devinette_affiche",
        "category": category,
        "content_type": content_type,
        "difficulty": difficulty,
        "prompt": "",
        "payload": {"poster_url": poster_url},
        "correct_answer": {"film": result["title"]},
        "requires_account": False,
    }


def generate_casting_question(
    title: str, difficulty: str, category: str, content_type: str = "film"
) -> dict:
    """Génère le JSON d'une question casting pour un film ou une série donné"""
    result = search_tv_show(title) if content_type == "serie" else search_movie(title)
    if result is None:
        raise ValueError(f"Introuvable sur TMDB : {title}")

    if content_type == "serie":
        cast = get_tv_show_cast(result["id"], limit=3)
    else:
        cast = get_movie_cast(result["id"], limit=3)

    actor_photos = [
        build_image_url(actor["profile_path"]) for actor in cast if actor["profile_path"]
    ]

    return {
        "mode": "casting",
        "category": category,
        "content_type": content_type,
        "difficulty": difficulty,
        "prompt": "",
        "payload": {"actor_photos": actor_photos},
        "correct_answer": {"film": result["title"]},
        "requires_account": False,
    }


if __name__ == "__main__":
    mode = sys.argv[1]
    title = sys.argv[2]
    difficulty = sys.argv[3] if len(sys.argv) > 3 else "moyen"
    category = sys.argv[4] if len(sys.argv) > 4 else "anecdote"
    content_type = sys.argv[5] if len(sys.argv) > 5 else "film"

    if mode == "affiche":
        question = generate_poster_question(title, difficulty, category, content_type)
    elif mode == "casting":
        question = generate_casting_question(title, difficulty, category, content_type)
    else:
        raise ValueError("Mode inconnu, utilise 'affiche' ou 'casting'")

    print(json.dumps(question, indent=2, ensure_ascii=False))