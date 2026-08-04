"""Modèles de données du moteur de jeu Filmatrix"""

from dataclasses import dataclass
from typing import Any 

@dataclass
class Question:
    """Représente une question générique, quel que soit le mode de jeu
    Le champs `payload` contient les données propores au mode (ex: les 4 options du QCM).
    Le champs `correct_answer` contient la bonne réponse, dans un format adapté au mode."""

    id: int
    mode: str 
    category: str 
    difficulty: str 
    prompt: str 
    payload: dict[str, Any]
    correct_answer: dict[str, Any]