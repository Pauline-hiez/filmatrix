"""Script utilitaire : génère le JSON d'une question Blind Test"""

import json
import sys

from dotenv import load_dotenv

from filmatrix.integrations.itunes import search_soundtrack_preview
from filmatrix.integrations.tmdb import search_movie, search_tv_show

load_dotenv()


def generate_blindtest_question(
    title: str,
    difficulty: str,
    category: str,
    music_search_term: str | None = None,
    content_type: str = "film",
) -> dict:
    """Génère le JSON d'une question Blind Test pour un film ou une série donné"""
    result = search_tv_show(title) if content_type == "serie" else search_movie(title)
    if result is None:
        raise ValueError(f"Introuvable sur TMDB : {title}")

    search_term = music_search_term or f"{title} soundtrack"
    preview_url = search_soundtrack_preview(search_term)
    if preview_url is None:
        raise ValueError(f"Aucun extrait audio trouvé pour : {search_term}")

    return {
        "mode": "blindtest",
        "category": category,
        "content_type": content_type,
        "difficulty": difficulty,
        "prompt": "",
        "payload": {"audio_url": preview_url},
        "correct_answer": {"film": result["title"]},
        "requires_account": False,
    }


if __name__ == "__main__":
    title = sys.argv[1]
    difficulty = sys.argv[2] if len(sys.argv) > 2 else "moyen"
    category = sys.argv[3] if len(sys.argv) > 3 else "anecdote"
    music_search_term = sys.argv[4] if len(sys.argv) > 4 else None
    content_type = sys.argv[5] if len(sys.argv) > 5 else "film"

    question = generate_blindtest_question(
        title, difficulty, category, music_search_term, content_type
    )

    print(json.dumps(question, indent=2, ensure_ascii=False))