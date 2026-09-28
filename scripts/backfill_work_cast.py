"""Rattrapage : peuple Work.cast pour les œuvres déjà en base.

get_or_create_work() ne renseigne le casting qu'à la création d'une Work -
celles créées avant l'ajout de ce champ (migration c2dc5952436e) restent avec
cast=[] tant que ce script n'a pas tourné. Idempotent par construction : ne
touche que les Work dont le cast est encore vide, un deuxième passage n'a
donc d'effet que sur celles ajoutées entre-temps (ou dont l'appel TMDB avait
échoué la première fois).

    python -m scripts.backfill_work_cast
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from filmatrix.extensions import db
from filmatrix.integrations.tmdb import get_movie_cast, get_tv_show_cast
from filmatrix.models import Work


def backfill_work_cast() -> None:
    works = Work.query.filter(
        db.or_(Work.cast.is_(None), Work.cast == [])
    ).all()

    updated = 0
    failed = 0
    for work in works:
        try:
            cast = get_movie_cast(work.tmdb_id) if work.content_type == "film" else get_tv_show_cast(work.tmdb_id)
        except Exception as exc:
            failed += 1
            print(f"  échec {work.title!r} (tmdb_id={work.tmdb_id}) : {exc}")
            continue

        if not cast:
            continue

        work.cast = [actor["name"] for actor in cast]
        db.session.commit()
        updated += 1
        print(f"  {work.title!r} -> {len(work.cast)} acteur(s)")

    print(f"\n{updated} Work mise(s) à jour, {failed} échec(s), {len(works) - updated - failed} sans casting TMDB.")


def main() -> None:
    # Importé ici plutôt qu'en tête de module - même raison que les autres
    # scripts de rattrapage (le monkey patching gevent ne doit pas s'exécuter
    # comme effet de bord d'un import par les tests).
    from wsgi import app

    with app.app_context():
        backfill_work_cast()


if __name__ == "__main__":
    main()
