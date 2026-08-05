"""Script d'import : lit data/questions.json et remplit la base de données"""

import json 

from app import app 
from src.database import db 
from src.models import Question 

def import_questions() -> None:
    """Charge les questions du JSON et les insère dans la base"""
    with open("data/questions.json", encoding="utf-8") as file:
        questions_json = json.load(file)

    with app.app_context():
        for data in questions_json:
            question = Question(
                id=data["id"],
                mode=data["mode"],
                category=data["category"],
                difficulty=data["difficulty"],
                prompt=data["prompt"],
                payload=data["payload"],
                correct_answer=data["correct_answer"],
                requires_account=data["requires_account"],
                )
            db.session.merge(question)
        db.session.commit()
        print(f"{len(questions_json)} question(s) importée(s) avec succès.")

if __name__ == "__main__":
    import_questions()