"""Script d'import : lit data/questions.json et remplit la base de données"""

import json 

from app import app 
from src.database import db 
from src.models import Question 

def importer_questions() -> None:
    """Charge les questions du JSON et les insère dans la base"""
    with open("data/questions.json", encoding="utf-8") as fichier:
        questions_json = json.load(fichier)

    with app.app_context(): 
        for donnees in questions_json:
            question = Question(
                id=donnees["id"],
                mode=donnees["mode"],
                category=donnees["category"],
                difficulty=donnees["difficulty"],
                prompt=donnees["prompt"],
                payload=donnees["payload"],
                correct_answer=donnees["correct_answer"],
                )
            db.session.merge(question)
        db.session.commit()
        print(f"{len(questions_json)} question(s) importée(s) avec succès.")

if __name__ == "__main__":
    importer_questions()