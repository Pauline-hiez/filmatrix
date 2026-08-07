"""Script utilitaire : génère le JSON d'une question Blind Test"""

import json
import sys

from dotenv import load_dotenv

from src.itunes import search_soundtrack_preview
from src.tmdb import search_movie

load_dotenv()


def generate_blindtest_question(
    movie_title: str, difficulty: str, category: str, music_search_term: str | None = None
) -> dict:
    """Génère le JSON d'une question Blind Test pour un film donné"""
    movie = search_movie(movie_title)
    if movie is None:
        raise ValueError(f"Film introuvable sur TMDB : {movie_title}")

    search_term = music_search_term or f"{movie_title} soundtrack"
    preview_url = search_soundtrack_preview(search_term)
    if preview_url is None:
        raise ValueError(f"Aucun extrait audio trouvé pour : {search_term}")

    return {
        "mode": "blindtest",
        "category": category,
        "difficulty": difficulty,
        "prompt": "",
        "payload": {"audio_url": preview_url},
        "correct_answer": {"film": movie["title"]},
        "requires_account": False,
    }


if __name__ == "__main__":
    title = sys.argv[1]
    difficulty = sys.argv[2] if len(sys.argv) > 2 else "moyen"
    category = sys.argv[3] if len(sys.argv) > 3 else "anecdote"
    music_search_term = sys.argv[4] if len(sys.argv) > 4 else None

    question = generate_blindtest_question(title, difficulty, category, music_search_term)

    print(json.dumps(question, indent=2, ensure_ascii=False))