"""Tests du script de rattrapage du casting (scripts/backfill_work_cast.py)
pour les Work créées avant l'ajout du champ Work.cast."""

from unittest.mock import patch

from filmatrix.extensions import db
from filmatrix.models import Work
from scripts.backfill_work_cast import backfill_work_cast


def create_work(tmdb_id: int, content_type: str = "film", cast: list[str] | None = None) -> Work:
    work = Work(
        tmdb_id=tmdb_id,
        content_type=content_type,
        title=f"Œuvre {tmdb_id}",
        poster_url=f"https://example.com/{tmdb_id}.jpg",
        genres=[],
        cast=cast or [],
    )
    db.session.add(work)
    db.session.commit()
    return work


def test_backfill_fills_cast_for_works_missing_it(app):
    """Une Work sans casting doit se voir remplie par le rattrapage."""
    with app.app_context():
        work = create_work(100, cast=[])
        work_id = work.id

        cast_response = [{"name": "Brad Pitt"}, {"name": "Edward Norton"}]
        with patch("scripts.backfill_work_cast.get_movie_cast", return_value=cast_response):
            backfill_work_cast()

        assert Work.query.get(work_id).cast == ["Brad Pitt", "Edward Norton"]


def test_backfill_skips_works_that_already_have_a_cast(app):
    """Une Work déjà peuplée ne doit pas être retouchée (pas d'appel TMDB
    superflu, idempotence du rattrapage)."""
    with app.app_context():
        create_work(200, cast=["Déjà là"])

        with patch("scripts.backfill_work_cast.get_movie_cast") as mock_get_cast:
            backfill_work_cast()

        mock_get_cast.assert_not_called()


def test_backfill_uses_the_tv_credits_endpoint_for_series(app):
    """Une Work série doit passer par get_tv_show_cast, pas get_movie_cast."""
    with app.app_context():
        work = create_work(300, content_type="serie", cast=[])
        work_id = work.id

        with patch("scripts.backfill_work_cast.get_movie_cast") as mock_movie_cast, \
             patch("scripts.backfill_work_cast.get_tv_show_cast", return_value=[{"name": "Millie Bobby Brown"}]) as mock_tv_cast:
            backfill_work_cast()

        mock_movie_cast.assert_not_called()
        mock_tv_cast.assert_called_once_with(300)
        assert Work.query.get(work_id).cast == ["Millie Bobby Brown"]
