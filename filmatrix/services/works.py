"""Gestion des œuvres (Work) : création idempotente depuis TMDB et filtrage
saga/genre pour les questions.
"""

import json

from sqlalchemy.exc import IntegrityError

from filmatrix.extensions import db
from filmatrix.integrations.tmdb import build_image_url, get_movie_by_id, get_tv_show_by_id
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

    work = Work(
        tmdb_id=tmdb_id,
        content_type=content_type,
        title=details["title"],
        poster_url=build_image_url(details.get("poster_path")),
        genres=details.get("genres", []),
        saga=details.get("saga"),
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


def work_genre_filter(genre_name: str):
    """Condition SQLAlchemy filtrant Work.genres (JSON) sur un genre donné.

    Work.genres est un JSON générique (db.JSON), sans opérateur "contains"
    portable entre SQLite et PostgreSQL/Neon. On caste donc la colonne en
    texte et on cherche la sous-chaîne JSON-échappée du genre : ça fonctionne
    à l'identique sur les deux moteurs (JSON stocké en TEXT sur SQLite,
    CAST(... AS VARCHAR) valide sur json/jsonb en PostgreSQL)."""
    needle = json.dumps(genre_name)  # ex: '"Horreur"', guillemets inclus
    return db.cast(Work.genres, db.String).like(f"%{needle}%")
