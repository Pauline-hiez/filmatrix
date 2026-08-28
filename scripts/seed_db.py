"""Script d'import : lit tous les fichiers de data/questions/ et remplit la base de données"""

import json
from pathlib import Path

from wsgi import app
from filmatrix.extensions import db
from filmatrix.models import Question, Tag, question_tags


def project_root() -> Path:
    """Retourne la racine du projet, quel que soit le répertoire courant."""
    return Path(__file__).resolve().parents[1]


def import_questions() -> None:
    """Charge les questions de tous les fichiers JSON du dossier et les insère dans la base"""
    questions_folder = project_root() / "data" / "questions"
    json_files = sorted(questions_folder.glob("*.json"))

    total_imported = 0
    imported_ids: set[int] = set()

    with app.app_context():
        tag_aliases = {
            "Star Wars": "star-wars",
            "com" + "�" + "die": "comédie",
            "comédie": "comédie",
        }

        # Nettoie les anciennes associations créées par les imports précédents.
        # Elles seront reconstruites à partir des JSON actuels.
        from sqlalchemy import text
        db.session.execute(text("DELETE FROM question_tags"))
        db.session.flush()

        for json_file in json_files:
            with open(json_file, encoding="utf-8") as file:
                questions_json = json.load(file)

            for data in questions_json:
                imported_ids.add(data["id"])
                question = Question(
                    id=data["id"],
                    mode=data["mode"],
                    content_type=data.get("content_type", "film"),
                    prompt=data["prompt"],
                    payload=data["payload"],
                    correct_answer=data["correct_answer"],
                    requires_account=data["requires_account"],
                )

                # Les tags restent dans la base afin d'être réutilisables par
                # plusieurs questions et sélectionnables depuis l'écran de jeu.
                existing_question = Question.query.get(data["id"])
                if existing_question is not None:
                    existing_question.mode = question.mode
                    existing_question.content_type = question.content_type
                    existing_question.prompt = question.prompt
                    existing_question.payload = question.payload
                    existing_question.correct_answer = question.correct_answer
                    existing_question.requires_account = question.requires_account
                    question = existing_question
                else:
                    db.session.add(question)

                # Remplace les associations importées précédemment : le seed
                # doit rester idempotent quand le contenu JSON évolue.
                db.session.execute(
                    question_tags.delete().where(question_tags.c.question_id == question.id)
                )
                db.session.flush()

                for tag_data in data.get("tags", []):
                    if isinstance(tag_data, str):
                        tag_name = tag_data
                        tag_type = "autre"
                    else:
                        tag_name = tag_data["name"]
                        tag_type = tag_data.get("type", "autre")

                    tag_name = tag_aliases.get(tag_name, tag_name)
                    tag = Tag.query.filter_by(name=tag_name).first()
                    if tag is None:
                        tag = Tag(name=tag_name, tag_type=tag_type)
                        db.session.add(tag)
                        db.session.flush()
                    elif tag.tag_type == "autre" and tag_type != "autre":
                        tag.tag_type = tag_type

                    db.session.execute(
                        question_tags.insert().values(question_id=question.id, tag_id=tag.id)
                    )

            total_imported += len(questions_json)
            print(f"  {json_file.name} : {len(questions_json)} question(s)")

        db.session.commit()
        print(f"Total : {total_imported} question(s) importée(s) avec succès.")

        report_orphans(imported_ids)


def report_orphans(imported_ids: set[int]) -> None:
    """Signale les questions présentes en base mais absentes des fichiers JSON

    L'import est un upsert : il ne supprime rien. Une question retirée d'un JSON
    reste donc en base et continue d'être tirée en partie. On ne la supprime pas
    d'office — des tentatives et des signalements y sont rattachés — mais le
    silence serait pire : on les liste pour que la décision soit prise en connaissance de cause.
    """
    orphans = [
        row.id for row in Question.query.order_by(Question.id).all()
        if row.id not in imported_ids
    ]

    if not orphans:
        return

    apercu = ", ".join(str(i) for i in orphans[:15])
    suite = " ..." if len(orphans) > 15 else ""
    print()
    print(
        f"Attention : {len(orphans)} question(s) en base ne figurent plus dans "
        f"data/questions/. Elles restent jouables tant qu'elles ne sont pas "
        f"supprimées."
    )
    print(f"  ids : {apercu}{suite}")


if __name__ == "__main__":
    import_questions()