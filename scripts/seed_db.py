"""Script d'import : lit tous les fichiers de data/questions/ et remplit la base de données"""

import json
from pathlib import Path

from wsgi import app
from filmatrix.extensions import db
from filmatrix.models import Question


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
                db.session.merge(question)

            total_imported += len(questions_json)
            print(f"  {json_file.name} : {len(questions_json)} question(s)")

        db.session.commit()
        print(f"Total : {total_imported} question(s) importée(s) avec succès.")


if __name__ == "__main__":
    import_questions()