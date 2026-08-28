"""Script d'import : lit tous les fichiers de data/questions/ et remplit la base de données"""

import json
from pathlib import Path

from wsgi import app
from filmatrix.extensions import db
from filmatrix.models import Question, Tag


def import_questions() -> None:
    """Charge les questions de tous les fichiers JSON du dossier et les insère dans la base"""
    questions_folder = Path("data/questions")
    json_files = sorted(questions_folder.glob("*.json"))

    total_imported = 0

    with app.app_context():
        for json_file in json_files:
            with open(json_file, encoding="utf-8") as file:
                questions_json = json.load(file)

            for data in questions_json:
                question = Question(
                    id=data["id"],
                    mode=data["mode"],
                    category=data["category"],
                    content_type=data.get("content_type", "film"),
                    difficulty=data["difficulty"],
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
                    existing_question.category = question.category
                    existing_question.content_type = question.content_type
                    existing_question.difficulty = question.difficulty
                    existing_question.prompt = question.prompt
                    existing_question.payload = question.payload
                    existing_question.correct_answer = question.correct_answer
                    existing_question.requires_account = question.requires_account
                    existing_question.tags = []
                    question = existing_question
                else:
                    db.session.add(question)

                for tag_data in data.get("tags", []):
                    if isinstance(tag_data, str):
                        tag_name = tag_data
                        tag_type = "autre"
                    else:
                        tag_name = tag_data["name"]
                        tag_type = tag_data.get("type", "autre")

                    tag = Tag.query.filter_by(name=tag_name).first()
                    if tag is None:
                        tag = Tag(name=tag_name, tag_type=tag_type)
                        db.session.add(tag)
                    elif tag.tag_type == "autre" and tag_type != "autre":
                        tag.tag_type = tag_type

                    question.tags.append(tag)

            total_imported += len(questions_json)
            print(f"  {json_file.name} : {len(questions_json)} question(s)")

        db.session.commit()
        print(f"Total : {total_imported} question(s) importée(s) avec succès.")


if __name__ == "__main__":
    import_questions()