"""Recalcule les tags de genre de toutes les questions depuis TMDB.

Jusqu'ici chaque question ne portait qu'un seul genre, choisi à la main lors
de sa création : Alien n'avait que "science-fiction" (pas horreur), Predator
que "action", Les Dents de la mer que "thriller"... Le filtre par genre de
l'écran de préparation en souffrait directement : sélectionner « horreur » ne
renvoyait qu'une fraction des questions qui parlent pourtant bien d'un film
d'horreur.

Ce script retrouve l'œuvre dont parle chaque question, interroge TMDB pour ses
genres réels (une œuvre peut légitimement en avoir plusieurs : le modèle
question_tags le permet déjà, aucun changement de schéma nécessaire) et
remplace le tag "genre" existant par l'ensemble à jour.

Comment le sujet de la question est retrouvé selon le mode :
  - citation, emoji, devinette, devinette_affiche, casting, blindtest :
    directement dans correct_answer["film"].
  - film_melange : directement dans correct_answer["title"].
  - qcm, vrai_faux : ces deux modes ne stockent le titre nulle part, seulement
    du texte libre ("Dans X, ...", "Qui a réalisé X ?"...). Le titre est donc
    extrait par des motifs de texte, puis vérifié contre le résultat TMDB
    (correspondance floue ou préfixe) avant d'être exploité. Un motif qui ne
    correspond à aucun format connu, ou dont l'extraction ne retrouve aucune
    œuvre correspondante sur TMDB, est laissé de côté : mieux vaut ne rien
    changer que de poser un mauvais genre.
  - chronologie : une question porte sur quatre œuvres à la fois, pas sur une
    seule ; hors périmètre, son tag de genre décrit le thème de l'ensemble.

    python -m scripts.retag_genres
"""
import json
import re
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from filmatrix.integrations.tmdb import (
    genre_ids_to_tags,
    get_genre_maps,
    search_movie,
    search_tv_show,
)
from filmatrix.services.matching import fuzzy_match


def project_root() -> Path:
    """Retourne la racine du projet, quel que soit le répertoire courant."""
    return Path(__file__).resolve().parents[1]


BASE = project_root() / "data" / "questions"

# Le titre de l'œuvre est stocké directement pour ces modes.
FIELD_MODES = {
    "citation": "film",
    "emoji": "film",
    "devinette": "film",
    "devinette_affiche": "film",
    "casting": "film",
    "blindtest": "film",
    "film_melange": "title",
}
# Une question de chronologie porte sur quatre œuvres, pas sur une seule.
SKIP_MODES = {"chronologie"}

# Motifs de texte pour qcm/vrai_faux, du plus fréquent au plus rare. Ordonnés
# par précision décroissante ; le filtrage TMDB qui suit rattrape les
# extractions trop larges plutôt que de chercher la perfection ici.
PATTERNS = [
    re.compile(r"^Dans (?:la série |le film )?(.+?), "),
    re.compile(r"^Qui a réalisé (?:le film |la série )?(.+?)\s*\??$"),
    re.compile(r" dans (.+?)\s*\??$"),
    re.compile(r"^(?:Le film |La série )(.+?)\s(?:est|a |sort)"),
    re.compile(r" a réalisé (.+?)\.$"),
    re.compile(r" pour (.+?)\.$"),
    re.compile(r"^(.+?)\s(?:est réalisé|est sorti|est adapté|est un film|a remporté|compte)"),
]
INTERROGATIVES = {"quel", "quelle", "quels", "quelles", "qui", "combien", "comment", "où", "pourquoi", "de"}

# Titres dont le libellé français officiel diffère trop de celui utilisé dans
# nos questions pour que la recherche TMDB retombe naturellement dessus.
TITLE_OVERRIDES = {
    ("star wars", "film"): ("La Guerre des étoiles", None),
    ("halloween", "film"): ("La Nuit des masques", "1978"),
    ("wednesday", "serie"): ("Mercredi", None),
    ("chucky", "film"): ("Jeu d'enfant", "1988"),
    ("the wire", "serie"): ("Sur écoute", None),
    ("amélie poulain", "film"): ("Le Fabuleux Destin d'Amélie Poulain", None),
    ("amélie", "film"): ("Le Fabuleux Destin d'Amélie Poulain", None),
    ("silent hill", "film"): ("Silent Hill", "2006"),
    ("bridgerton", "serie"): ("La Chronique des Bridgerton", None),
    ("alien 3", "film"): ("Alien 3", "1992"),
    ("james bond", "film"): ("James Bond 007 contre Dr. No", None),
    ("le cercle", "film"): ("The Ring", "2002"),
}


def extract_subject(prompt: str) -> tuple[str, str | None] | tuple[None, None]:
    """Retrouve un titre d'œuvre plausible dans le texte libre d'un qcm/vrai_faux

    Renvoie (titre, année) si un motif connu correspond, (None, None) sinon.
    L'année n'est renvoyée que si le texte la précise explicitement entre
    parenthèses : elle sert ensuite à lever l'ambiguïté des remakes et suites
    partageant un même titre (Alien, Blade Runner...)."""
    for pattern in PATTERNS:
        match = pattern.search(prompt)
        if not match:
            continue
        raw = match.group(1).strip().rstrip(".,")
        year_match = re.search(r"\((\d{4})\)\s*$", raw)
        title = re.sub(r"\s*\(\d{4}\)\s*$", "", raw).strip()
        if not (2 <= len(title) <= 60):
            continue
        first_word = title.split()[0].lower().rstrip("?.,'")
        if first_word in INTERROGATIVES:
            continue
        return title, (year_match.group(1) if year_match else None)
    return None, None


def subject_of(question: dict) -> tuple[str, str | None] | tuple[None, None]:
    """Retourne (titre, année) de l'œuvre dont parle une question, si connu"""
    mode = question["mode"]
    if mode in SKIP_MODES:
        return None, None
    if mode in FIELD_MODES:
        return question["correct_answer"].get(FIELD_MODES[mode]), None
    if mode in ("qcm", "vrai_faux"):
        return extract_subject(question["prompt"])
    return None, None


FRANCHISE_CONTINUATIONS = (":", ",", "-", "et ", "and ", "(")


def titles_match(candidate: str, tmdb_title: str) -> bool:
    """Vérifie qu'un titre extrait correspond bien au résultat TMDB retourné

    Une correspondance floue attrape les petites variations d'orthographe.
    Un titre qui n'est que le début du titre TMDB couvre les sagas citées
    sans numéro d'épisode (« Harry Potter » face à « Harry Potter et la
    Coupe de feu »), mais seulement si la suite ressemble à un sous-titre
    de franchise : un simple mot ajouté peut aussi bien désigner un tout
    autre film (« Le Cercle » n'est pas « Le Cercle rouge »)."""
    if fuzzy_match(candidate, tmdb_title):
        return True

    candidate_lower, title_lower = candidate.strip().lower(), tmdb_title.strip().lower()
    if not title_lower.startswith(candidate_lower):
        return False

    remainder = title_lower[len(candidate_lower):].lstrip()
    return remainder != "" and remainder.startswith(FRANCHISE_CONTINUATIONS)


def build_resolver():
    """Construit la fonction de résolution titre -> tags de genre, avec cache

    Le cache évite de répéter le même appel TMDB pour chaque question qui
    partage la même œuvre — l'essentiel du volume, une bonne partie du
    catalogue tournant autour d'un nombre restreint de films et de séries."""
    movie_genres, tv_genres = get_genre_maps()
    cache: dict[tuple[str, str | None, str], tuple[list[str] | None, str]] = {}

    def resolve(title: str, year: str | None, content_type: str) -> tuple[list[str] | None, str]:
        key = (title.lower(), year, content_type)
        if key in cache:
            return cache[key]

        override = TITLE_OVERRIDES.get((title.lower(), content_type))
        query, override_year = override if override else (title, year)
        result = (
            search_tv_show(query, override_year)
            if content_type == "serie"
            else search_movie(query, override_year)
        )

        tags, reason = None, "aucun résultat TMDB"
        if result:
            if override or titles_match(title, result["title"]):
                genre_map = tv_genres if content_type == "serie" else movie_genres
                found = genre_ids_to_tags(result["genre_ids"], genre_map)
                tags = found or None
                reason = "ok" if found else "TMDB sans genre exploitable"
            else:
                reason = f"pas de correspondance (TMDB a renvoyé {result['title']!r})"

        cache[key] = (tags, reason)
        time.sleep(0.05)
        return cache[key]

    return resolve


def replace_genre_tags(question: dict, new_genres: list[str]) -> bool:
    """Remplace les tags de genre d'une question, en conservant les autres

    Renvoie True si le contenu a réellement changé, pour ne compter et ne
    réécrire que ce qui a bougé."""
    old_tags = question.get("tags", [])
    prefix = [t for t in old_tags if t.get("type") in ("univers", "saga")]
    suffix = [t for t in old_tags if t.get("type") not in ("univers", "saga", "genre")]
    new_tags = prefix + [{"name": g, "type": "genre"} for g in new_genres] + suffix

    if new_tags == old_tags:
        return False

    question["tags"] = new_tags
    return True


def retag_all() -> None:
    resolve = build_resolver()

    files_changed = 0
    stats = {"sans_sujet": 0, "non_resolu": 0, "resolu": 0, "inchange": 0}
    unresolved: list[tuple[str, int, str, str]] = []

    for json_file in sorted(BASE.glob("*.json")):
        data = json.loads(json_file.read_text(encoding="utf-8"))
        file_changed = False

        for question in data:
            subject, year = subject_of(question)
            if subject is None:
                stats["sans_sujet"] += 1
                continue

            genres, reason = resolve(subject, year, question.get("content_type", "film"))
            if genres is None:
                stats["non_resolu"] += 1
                unresolved.append((json_file.name, question["id"], subject, reason))
                continue

            stats["resolu"] += 1
            if replace_genre_tags(question, genres):
                file_changed = True
            else:
                stats["inchange"] += 1

        if file_changed:
            json_file.write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            files_changed += 1
            print(f"  {json_file.name} : mis à jour")

    print(f"\n{files_changed} fichier(s) modifié(s).")
    print(f"Bilan : {stats['resolu']} question(s) avec des genres à jour "
          f"({stats['inchange']} déjà corrects), {stats['sans_sujet']} sans "
          f"œuvre identifiable, {stats['non_resolu']} non résolue(s).")

    if unresolved:
        print(f"\n{len(unresolved)} question(s) non résolue(s) — genre inchangé :")
        for name, qid, subject, reason in unresolved:
            print(f"  {name}#{qid} : {subject!r} -> {reason}")


if __name__ == "__main__":
    retag_all()
