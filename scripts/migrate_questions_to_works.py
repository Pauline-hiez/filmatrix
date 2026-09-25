"""Rattache les questions existantes à une Work TMDB (script de rattrapage).

Avant l'introduction de Work, le classement saga/genre reposait uniquement
sur des Tag posés à la main. Ce script relie rétroactivement chaque Question
sans work_id à l'œuvre TMDB correspondante :

- Regroupe les questions sans work_id par (titre, content_type), le titre
  venant de correct_answer["film"] ou correct_answer["title"] selon le mode
  (cf. services/engine.py) - qcm, vrai_faux et chronologie n'ont ni l'un ni
  l'autre et sont donc loguées à part, comme "sans titre exploitable".
- Cherche l'œuvre correspondante sur TMDB (search_movie / search_tv_show) et
  crée/récupère sa Work via get_or_create_work.
- Relie toutes les questions du groupe à cette Work.
- Logue les titres sans correspondance TMDB, pour traitement manuel a
  posteriori.

Ne touche jamais question.tags : les tags existants restent en place tant
que la transition n'est pas confirmée complète. Idempotent : ne porte que
sur work_id IS NULL, et get_or_create_work ne duplique jamais une Work -
relancer ce script n'a d'effet que sur les questions qui n'ont pas encore
trouvé de correspondance.

    python -m scripts.migrate_questions_to_works
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from filmatrix.extensions import db
from filmatrix.integrations.tmdb import search_movie, search_tv_show
from filmatrix.models import Question
from filmatrix.services.works import get_or_create_work


def extract_title(question: Question) -> str | None:
    """Titre exploitable d'une question, ou None si son mode n'en porte pas
    (qcm, vrai_faux, chronologie - cf. services/engine.py)."""
    answer = question.correct_answer or {}
    return answer.get("film") or answer.get("title")


def migrate_questions_to_works() -> None:
    questions = Question.query.filter(Question.work_id.is_(None)).all()

    groups: dict[tuple[str, str], list[Question]] = {}
    untitled_count = 0
    for question in questions:
        title = extract_title(question)
        if not title:
            untitled_count += 1
            continue
        groups.setdefault((title, question.content_type), []).append(question)

    linked_count = 0
    unmatched: list[tuple[str, str, int]] = []

    for (title, content_type), group_questions in groups.items():
        result = search_movie(title) if content_type == "film" else search_tv_show(title)

        if result is None:
            unmatched.append((title, content_type, len(group_questions)))
            continue

        work = get_or_create_work(result["id"], content_type)
        for question in group_questions:
            question.work_id = work.id
        db.session.commit()
        linked_count += len(group_questions)
        print(f"  {title!r} ({content_type}) -> Work #{work.id} : {len(group_questions)} question(s)")

    print(f"\n{linked_count} question(s) rattachée(s), {untitled_count} sans titre exploitable.")

    if unmatched:
        print(f"\n{len(unmatched)} titre(s) sans correspondance TMDB :")
        for title, content_type, count in unmatched:
            print(f"  - {title!r} ({content_type}) : {count} question(s)")


def main() -> None:
    # Importé ici plutôt qu'en tête de module : le monkey patching gevent de
    # wsgi.py ne doit s'exécuter qu'en lancement direct du script, jamais
    # comme effet de bord de l'import de migrate_questions_to_works() par les
    # tests (cf. tests/test_works.py), sous peine de corrompre l'état SSL
    # pour le reste de la session pytest (RecursionError dans requests/ssl).
    from wsgi import app

    with app.app_context():
        migrate_questions_to_works()


if __name__ == "__main__":
    main()
