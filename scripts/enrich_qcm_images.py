"""Enrichit les réponses QCM avec des images TMDB fiables.

Le script ne touche qu'aux questions de `data/questions/qcm*.json` et n'ajoute une
image que lorsque le type de question indique clairement qu'une proposition est
un film, une série, un acteur ou un réalisateur. Les correspondances TMDB sont
validées par nom normalisé exact : une recherche approchante n'est jamais écrite.

Usage :
    python -m scripts.enrich_qcm_images
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

from dotenv import load_dotenv

from filmatrix.integrations.tmdb import (
    build_image_url,
    search_movies_list,
    search_people_list,
    search_tv_shows_list,
)

load_dotenv()

BASE = Path(__file__).resolve().parents[1] / "data" / "questions"
QCM_FILES = (BASE / "qcm.json", BASE / "qcm_serie.json")

DIRECTOR_PATTERN = re.compile(r"\b(r[ée]alisateur|r[ée]alisatrice|r[ée]alis[ée]|sign[ée])\b", re.I)
ACTOR_PATTERN = re.compile(
    r"\b(acteur|actrice|incarne|interpr[èe]te|joue le r[ôo]le|qui joue)\b", re.I
)
WORK_PATTERN = re.compile(
    r"\b(quel film|quelle s[ée]rie|de quel film|de quelle s[ée]rie|quelle saga|quel [ée]pisode|quel long m[ée]trage)\b",
    re.I,
)


def normalize(value: str) -> str:
    """Normalise accents, ponctuation et espaces pour comparer deux noms."""
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    without_accents = "".join(
        char for char in decomposed if not unicodedata.combining(char)
    )
    return " ".join(
        "".join(char if char.isalnum() else " " for char in without_accents).split()
    )


def question_kind(prompt: str) -> str | None:
    """Détermine le type d'image autorisé par l'énoncé, sans deviner le sujet."""
    lowered = prompt.casefold()
    if "personnage" in lowered or "personnes" in lowered:
        return None
    if DIRECTOR_PATTERN.search(prompt):
        return "person"
    if ACTOR_PATTERN.search(prompt):
        return "person"
    if WORK_PATTERN.search(prompt):
        return "work"
    return None


def image_for_work(title: str, content_type: str, cache: dict) -> str | None:
    """Retourne l'affiche d'un film ou d'une série après correspondance exacte."""
    key = ("work", content_type, normalize(title))
    if key in cache:
        return cache[key]

    results = (
        search_tv_shows_list(title, limit=5)
        if content_type == "serie"
        else search_movies_list(title, limit=5)
    )
    wanted = normalize(title)
    image_url = None
    for result in results:
        if normalize(result["title"]) == wanted and result.get("thumbnail_url"):
            image_url = result["thumbnail_url"]
            break

    cache[key] = image_url
    return image_url


def image_for_person(name: str, cache: dict) -> str | None:
    """Retourne le portrait d'une personne après correspondance exacte."""
    key = ("person", normalize(name))
    if key in cache:
        return cache[key]

    results = search_people_list(name, limit=5)
    wanted = normalize(name)
    image_url = None
    for result in results:
        if normalize(result["name"]) == wanted and result.get("profile_url"):
            image_url = result["profile_url"]
            break

    cache[key] = image_url
    return image_url


def enrich_question(question: dict, cache: dict) -> tuple[bool, int, int]:
    """Enrichit une question et renvoie (modifiée, images ajoutées, recherches)."""
    kind = question_kind(question.get("prompt", ""))
    if question.get("mode") != "qcm" or kind is None:
        return False, 0, 0

    options = question.get("payload", {}).get("options", [])
    if not options or not all(isinstance(option, str) for option in options):
        return False, 0, 0

    existing = question["payload"].get("option_images")
    if isinstance(existing, list):
        option_images = list(existing) + [None] * (len(options) - len(existing))
        option_images = option_images[: len(options)]
    else:
        option_images = [None] * len(options)

    added = 0
    for index, option in enumerate(options):
        if option_images[index]:
            continue

        if kind == "work":
            image_url = image_for_work(option, question.get("content_type", "film"), cache)
        else:
            # Les propositions composées (duos, listes, métiers...) ne sont pas
            # des personnes identifiables par une seule recherche TMDB.
            if any(separator in option for separator in (" et ", " / ", ",")):
                continue
            image_url = image_for_person(option, cache)

        if image_url:
            option_images[index] = image_url
            added += 1

    if not added:
        return False, 0, len(cache)

    question["payload"]["option_images"] = option_images
    return True, added, len(cache)


def enrich_file(path: Path, cache: dict) -> tuple[int, int]:
    """Enrichit un fichier JSON et le réécrit uniquement s'il a changé."""
    questions = json.loads(path.read_text(encoding="utf-8"))
    changed_questions = 0
    added_images = 0

    for question in questions:
        changed, added, _ = enrich_question(question, cache)
        if changed:
            changed_questions += 1
            added_images += added

    if changed_questions:
        path.write_text(
            json.dumps(questions, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    return changed_questions, added_images


def main() -> None:
    """Enrichit les deux catalogues QCM et affiche un bilan détaillé."""
    cache: dict = {}
    total_questions = 0
    total_images = 0

    for path in QCM_FILES:
        changed, added = enrich_file(path, cache)
        total_questions += changed
        total_images += added
        print(f"{path.name}: {changed} question(s), {added} image(s) ajoutée(s)")

    print(f"Total: {total_questions} question(s) enrichie(s), {total_images} image(s) ajoutée(s)")
    print(f"Correspondances TMDB mises en cache: {len(cache)}")


if __name__ == "__main__":
    main()
