"""Script de nettoyage : supprime les questions présentes en base mais absentes
des fichiers JSON de data/questions/.

L'import (scripts/seed_db.py) est un upsert qui ne supprime jamais rien : une
question retirée d'un JSON reste en base et continue d'être tirée en partie.
Ce script supprime ces questions orphelines, ainsi que les tentatives (Attempt),
signalements (Report), tags et questions de partie multijoueur qui leur sont
rattachés.

Ce nettoyage efface de l'historique réel de jeu (les réponses déjà données par
les joueurs sur ces questions précises) : par défaut, le script ne fait qu'un
état des lieux (dry-run). Ajouter --confirm pour supprimer réellement.

    python -m scripts.delete_orphan_questions          (aperçu, ne supprime rien)
    python -m scripts.delete_orphan_questions --confirm (supprime réellement)
"""

import json
import sys
from pathlib import Path

from wsgi import app
from filmatrix.extensions import db
from filmatrix.models import Attempt, GameSessionQuestion, Question, Report, question_tags


def project_root() -> Path:
    """Retourne la racine du projet, quel que soit le répertoire courant."""
    return Path(__file__).resolve().parents[1]


def imported_ids() -> set[int]:
    """Recalcule l'ensemble des id présents dans data/questions/*.json"""
    ids: set[int] = set()
    for json_file in (project_root() / "data" / "questions").glob("*.json"):
        with open(json_file, encoding="utf-8") as file:
            for data in json.load(file):
                ids.add(data["id"])
    return ids


def delete_orphans(confirm: bool) -> None:
    with app.app_context():
        current_ids = imported_ids()
        orphan_ids = [
            row.id for row in Question.query.order_by(Question.id).all()
            if row.id not in current_ids
        ]

        if not orphan_ids:
            print("Aucune question orpheline : la base correspond exactement aux JSON.")
            return

        attempts = Attempt.query.filter(Attempt.question_id.in_(orphan_ids)).count()
        reports = Report.query.filter(Report.question_id.in_(orphan_ids)).count()
        session_questions = GameSessionQuestion.query.filter(
            GameSessionQuestion.question_id.in_(orphan_ids)
        ).count()

        print(f"{len(orphan_ids)} question(s) orpheline(s) trouvée(s).")
        print(f"  Rattachés : {attempts} tentative(s), {reports} signalement(s), "
              f"{session_questions} question(s) de partie multijoueur.")

        if not confirm:
            apercu = ", ".join(str(i) for i in orphan_ids[:20])
            suite = " ..." if len(orphan_ids) > 20 else ""
            print(f"  ids : {apercu}{suite}")
            print("\nAucune suppression effectuée (dry-run). Relancer avec --confirm pour supprimer.")
            return

        db.session.execute(
            question_tags.delete().where(question_tags.c.question_id.in_(orphan_ids))
        )
        Attempt.query.filter(Attempt.question_id.in_(orphan_ids)).delete(synchronize_session=False)
        Report.query.filter(Report.question_id.in_(orphan_ids)).delete(synchronize_session=False)
        GameSessionQuestion.query.filter(
            GameSessionQuestion.question_id.in_(orphan_ids)
        ).delete(synchronize_session=False)
        Question.query.filter(Question.id.in_(orphan_ids)).delete(synchronize_session=False)

        db.session.commit()
        print(f"\n{len(orphan_ids)} question(s) supprimée(s) avec succès.")


if __name__ == "__main__":
    delete_orphans(confirm="--confirm" in sys.argv)
