"""Ajoute une image de contexte aux questions portant sur une œuvre identifiable.

Les URLs sont stockées dans ``payload.question_image_url``. Le script privilégie
les images déjà présentes dans les données, puis interroge TMDB avec un cache.
Une question générale (par exemple « quel film a gagné l'Oscar en 2020 ? ») n'est
pas enrichie lorsqu'aucune œuvre unique ne peut être identifiée.

Certains modes (citation, devinette, film_melange, blindtest, devinette_affiche,
casting, emoji) demandent au joueur de deviner l'œuvre elle-même : la réponse
correcte (``correct_answer``) ne doit alors JAMAIS servir de candidat, sous
peine d'illustrer la question avec l'affiche de sa propre réponse. Ces modes
n'affichent d'ailleurs pas ce champ (voir question_image_url dans
filmatrix/services/questions.py, qui retombe sur une icône de mode générique
pour eux) : ce script ne les enrichit donc plus du tout.

Usage:
    python -m scripts.enrich_question_images
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

from dotenv import load_dotenv

from filmatrix.integrations.tmdb import build_image_url, search_movie, search_tv_show

load_dotenv()

BASE = Path(__file__).resolve().parents[1] / "data" / "questions"
FILES = tuple(sorted(BASE.glob("*.json")))

# Certaines formulations désignent une franchise plutôt qu'un titre TMDB exact.
# Elles sont volontairement limitées à des univers très connus : l'image choisie
# représente alors l'œuvre de référence la plus identifiable de la franchise.
TITLE_ALIASES = {
    "marvel cinematic universe": "Iron Man",
    "harry potter": "Harry Potter à l'école des sorciers",
    "star wars": "Star Wars",
    "the hobbit": "Le Hobbit : Un voyage inattendu",
    "x men": "X-Men",
    "spider man": "Spider-Man",
    "pirates des caraibes": "Pirates des Caraïbes : La Malédiction du Black Pearl",
    "la saga saw": "Saw",
    "men in black": "Men in Black",
    "james bond": "James Bond 007 contre Dr No",
    "the mask": "The Mask",
    "the truman show": "The Truman Show",
    "a star is born": "A Star Is Born",
    "john wick": "John Wick",
    "the wire": "The Wire",
    "mad men": "Mad Men",
    "famille d abord": "Famille d'abord",
    "la flamme": "La Flamme",
    "le flambeau": "Le Flambeau",
    "scrubs": "Scrubs",
    "you": "You",
    "that 70 s show": "That '70s Show",
    "la petite maison dans la prairie": "La Petite Maison dans la prairie",
    "le prince de bel air": "Le Prince de Bel-Air",
    "shameless": "Shameless",
    "h": "H",
}

EXPLICIT_TITLE_PATTERNS = (
    re.compile(r"\bdans\s+(?:la série|le film)\s+(.+?)(?:,|\?|$)", re.IGNORECASE),
    re.compile(r"\bdans\s+(.+?)(?:,\s*(?:quel|quelle|qui|comment|où)|\?|$)", re.IGNORECASE),
    re.compile(r"\b(?:réalisé|réalisée|signé|signée)\s+(?:le film\s+)?(.+?)(?:\s*\(|\s*\?|$)", re.IGNORECASE),
)


def normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    plain = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join("".join(char if char.isalnum() else " " for char in plain).split())


def title_key(value: str) -> str:
    """Normalise aussi les années pour comparer un titre à une réponse TMDB."""
    return re.sub(r"\b(?:19|20)\d{2}\b", "", normalize(value)).strip()


def collect_titles() -> set[str]:
    """Collecte les titres rencontrés dans le catalogue, avec ou sans image."""
    titles: set[str] = set()
    for path in FILES:
        try:
            questions = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        for question in questions:
            answer = question.get("correct_answer") or {}
            for key in ("film", "title"):
                if isinstance(answer.get(key), str):
                    titles.add(answer[key])
            films = (question.get("payload") or {}).get("films", [])
            if isinstance(films, list):
                titles.update(film for film in films if isinstance(film, str))
    return titles


def known_images() -> dict[str, str]:
    """Indexe les affiches déjà enregistrées dans les fichiers JSON."""
    result: dict[str, str] = {}
    for path in FILES:
        try:
            questions = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        for question in questions:
            payload = question.get("payload") or {}
            image = payload.get("question_image_url") or payload.get("poster_url")
            answer = question.get("correct_answer") or {}
            title = answer.get("film") or answer.get("title")
            if image and isinstance(title, str):
                result.setdefault(title_key(title), image)
    return result


def clean_candidate(candidate: str) -> str:
    candidate = candidate.strip(" .,:;()[]«»\"")
    candidate = re.sub(r"^(?:la série|le film|la saga)\s+", "", candidate, flags=re.IGNORECASE)
    candidate = re.sub(r"\s+\([^)]*$", "", candidate)
    candidate = re.split(
        r"\s+(?:produite|produit|diffusée|diffusé|version|quelle|quel|qui|comment|où|est|a-t-il|exerce|s'appelle|surnomme)\b",
        candidate,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    return candidate.strip(" .,:;()[]«»\"")


def prompt_title_candidates(prompt: str, titles: set[str]) -> list[str]:
    """Retourne les œuvres explicitement visibles dans l'énoncé."""
    prompt_key = normalize(prompt)
    candidates: list[str] = []

    # Les titres présents dans le catalogue sont plus fiables que l'extraction
    # heuristique et couvrent les apostrophes, accents et années.
    for title in titles:
        key = title_key(title)
        if len(key) >= 4 and re.search(r"(?<![a-z0-9])" + re.escape(key) + r"(?![a-z0-9])", prompt_key):
            candidates.append(title)

    for alias_key, canonical_title in TITLE_ALIASES.items():
        pattern = r"(?<![a-z0-9])" + re.escape(alias_key) + r"(?![a-z0-9])"
        if re.search(pattern, prompt_key):
            candidates.append(canonical_title)

    for pattern in EXPLICIT_TITLE_PATTERNS:
        for match in pattern.finditer(prompt):
            candidate = clean_candidate(match.group(1))
            if 1 <= len(candidate.split()) <= 10 and len(title_key(candidate)) >= 3:
                candidates.append(candidate)

    unique: dict[str, str] = {}
    for candidate in candidates:
        unique.setdefault(title_key(candidate), candidate)
    return sorted(unique.values(), key=lambda value: len(title_key(value)), reverse=True)


def image_for_title(title: str, content_type: str, cache: dict, local_images: dict[str, str]) -> str | None:
    """Résout une affiche locale ou TMDB, avec validation prudente du résultat."""
    key = ("image", content_type, title_key(title))
    if key in cache:
        return cache[key]

    local = local_images.get(title_key(title))
    if local:
        cache[key] = local
        return local

    search_title = TITLE_ALIASES.get(title_key(title), title)
    result = (
        search_tv_show(search_title)
        if content_type == "serie"
        else search_movie(search_title)
    )
    image = None
    if result:
        returned_key = title_key(result.get("title", ""))
        wanted_key = title_key(search_title)
        is_exact = returned_key == wanted_key
        is_curated_alias = title_key(title) in TITLE_ALIASES
        if (is_exact or is_curated_alias) and result.get("poster_path"):
            image = build_image_url(result["poster_path"])

    cache[key] = image
    return image


# Modes où l'œuvre elle-même est la réponse à deviner : jamais illustrés par
# ce script, quelle que soit la source envisagée pour l'image (voir le
# docstring du module).
SPOILER_RISK_MODES = {
    "citation",
    "devinette",
    "film_melange",
    "blindtest",
    "devinette_affiche",
    "casting",
    "emoji",
}


def enrich_question(
    question: dict,
    titles: set[str],
    local_images: dict[str, str],
    cache: dict,
) -> bool:
    mode = question.get("mode")
    if mode in SPOILER_RISK_MODES:
        return False

    payload = question.setdefault("payload", {})
    if payload.get("question_image_url") or payload.get("poster_url"):
        return False

    content_type = question.get("content_type", "film")
    answer = question.get("correct_answer") or {}

    # Titre de la réponse comme candidat : sûr uniquement parce que ces modes
    # (qcm, vrai_faux, chronologie...) ne demandent jamais de deviner l'œuvre
    # elle-même — voir SPOILER_RISK_MODES ci-dessus pour les modes exclus.
    candidates: list[str] = []
    answer_title = answer.get("film") or answer.get("title")
    if isinstance(answer_title, str):
        candidates.append(answer_title)

    candidates.extend(prompt_title_candidates(question.get("prompt", ""), titles))

    seen: set[str] = set()
    for title in candidates:
        key = title_key(title)
        if not key or key in seen:
            continue
        seen.add(key)
        image = image_for_title(title, content_type, cache, local_images)
        if image:
            payload["question_image_url"] = image
            return True

    return False


def main() -> None:
    titles = collect_titles()
    local_images = known_images()
    cache: dict = {}
    total = 0

    for path in FILES:
        questions = json.loads(path.read_text(encoding="utf-8"))
        changed = sum(enrich_question(question, titles, local_images, cache) for question in questions)
        if changed:
            path.write_text(
                json.dumps(questions, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        total += changed
        print(f"{path.name}: {changed} image(s) ajoutée(s)")

    print(f"Total: {total} question(s) enrichie(s)")
    print(f"Recherches TMDB mises en cache: {len(cache)}")


if __name__ == "__main__":
    main()
