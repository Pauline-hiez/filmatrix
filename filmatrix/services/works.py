"""Gestion des œuvres (Work) : création idempotente depuis TMDB et filtrage
saga/genre pour les questions.
"""

import json

from sqlalchemy.exc import IntegrityError

from filmatrix.extensions import db
from filmatrix.integrations.tmdb import (
    build_image_url,
    get_movie_by_id,
    get_movie_cast,
    get_tv_show_by_id,
    get_tv_show_cast,
)
from filmatrix.models import Work


def get_or_create_work(tmdb_id: int, content_type: str) -> Work:
    """Récupère l'œuvre existante pour ce tmdb_id+content_type, ou la crée en
    interrogeant TMDB pour remplir titre, affiche, genres et saga.

    Idempotent : deux appels avec le même tmdb_id+content_type ne créent
    jamais de doublon, y compris en cas d'appels concurrents (protégé par la
    contrainte d'unicité en base)."""
    existing = Work.query.filter_by(tmdb_id=tmdb_id, content_type=content_type).first()
    if existing:
        return existing

    details = get_movie_by_id(tmdb_id) if content_type == "film" else get_tv_show_by_id(tmdb_id)
    cast = get_movie_cast(tmdb_id) if content_type == "film" else get_tv_show_cast(tmdb_id)

    work = Work(
        tmdb_id=tmdb_id,
        content_type=content_type,
        title=details["title"],
        poster_url=build_image_url(details.get("poster_path")),
        genres=details.get("genres", []),
        saga=details.get("saga"),
        cast=[actor["name"] for actor in cast],
    )
    db.session.add(work)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        existing = Work.query.filter_by(tmdb_id=tmdb_id, content_type=content_type).first()
        if existing:
            return existing
        raise

    return work


def resolve_point_commun_works(form) -> list[dict] | None:
    """Résout les 3 œuvres du mode Point commun depuis un formulaire (admin
    ou suggestion joueur) portant work_tmdb_id_1..3 / work_content_type_1..3,
    via get_or_create_work - jamais côté client, voir
    static/js/admin_question_form.js.

    Renvoie None si l'une des 3 n'est pas renseignée : le mode ne peut pas
    être enregistré sans ses 3 œuvres."""
    works = []
    for i in range(1, 4):
        tmdb_id = form.get(f"work_tmdb_id_{i}", type=int)
        if not tmdb_id:
            return None
        content_type = form.get(f"work_content_type_{i}", "film")
        work = get_or_create_work(tmdb_id, content_type)
        works.append({
            "work_id": work.id,
            "tmdb_id": work.tmdb_id,
            "content_type": work.content_type,
            "title": work.title,
            "poster_url": work.poster_url,
        })
    return works


def work_genre_filter(genre_name: str):
    """Condition SQLAlchemy filtrant Work.genres (JSON) sur un genre donné.

    Work.genres est un JSON générique (db.JSON), sans opérateur "contains"
    portable entre SQLite et PostgreSQL/Neon. On caste donc la colonne en
    texte et on cherche la sous-chaîne JSON-échappée du genre : ça fonctionne
    à l'identique sur les deux moteurs (JSON stocké en TEXT sur SQLite,
    CAST(... AS VARCHAR) valide sur json/jsonb en PostgreSQL)."""
    needle = json.dumps(genre_name)  # ex: '"Horreur"', guillemets inclus
    return db.cast(Work.genres, db.String).like(f"%{needle}%")
