"""Script utilitaire : vérifie et régénère les URLs audio expirées du blind test"""

import requests

from app import app
from src.database import db 
from src.itunes import search_soundtrack_preview
from src.models import Question

def is_url_valid(url: str) -> bool:
    """Vérifie qu'une URL audio répond correctement, sans télécharger le fichier entier"""
    try:
        response = requests.head(url, timeout=5)
        return response.status_code == 200
    except requests.RequestException:
        return False

def refresh_broken_urls() -> None:
    """Parcourt toutes les questions blind test et régénère les URLs cassées"""
    with app.app_context():
        blindtest_questions = Question.query.filter_by(mode="blindtest").all()

        for question in blindtest_questions:
            current_url = question.payload["audio_url"]
            film_title = question.correct_answer["film"]

            if is_url_valid(current_url):
                print(f" OK : {film_title}")
                continue

            print(f" CASSÉE : {film_title} - régénération en cours...")
            new_url = search_soundtrack_preview(f"{film_title} soundtrack")

            if new_url is None:
                print(f" ÉCHEC : aucun nouvel extrait trouvé pour {film_title}")
                continue

            question.payload = {"audio_url": new_url}
            db.session.commit()
            print(" CORRIGÉ : {film_title}")

if __name__ == "__main__":
    refresh_broken_urls()