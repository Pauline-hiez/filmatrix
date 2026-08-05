"""Moteur de jeu : vérifie si une réponse donnée par le joueur est correcte"""

from typing import Any 
from src.models import Question

def check_answer(question: Question, user_response: Any) -> bool:
    """Vérifie la réponse du joueur selon le mode de la question
    
    Args: question: la question posée (contient la mode et la bonne réponse)
          user_response: la réponse fournie par le joueur
          
    Returns: True si la réponse est correcte, sinon False
    
    Raises: ValueError: si le mode de la question n'est pas géré"""

    match question.mode:
        case "qcm":
            #Pour un QCM, la bonne réponse est l'index de l'option correcte
            return user_response == question.correct_answer["index"]

        case "vrai_faux":
            #Pour un vrai/faux, la bonne réponse est un booléen
            return user_response == question.correct_answer["value"]

        case "citation":
                    expected_answer = question.correct_answer["film"].strip().lower()
                    given_answer = user_response.strip().lower()
                    return given_answer == expected_answer

        case _:
            raise ValueError(f"Mode de question inconnu : {question.mode}")

        