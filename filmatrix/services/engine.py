"""Moteur de jeu : vérifie si une réponse donnée par le joueur est correcte"""

import random
from typing import Any

from src.matching import fuzzy_match
from src.models import Question


def check_answer(question: Question, user_response: Any) -> bool:
    """Vérifie la réponse du joueur selon le mode de la question

    Args: question: la question posée (contient la mode et la bonne réponse)
          user_response: la réponse fournie par le joueur

    Returns: True si la réponse est correcte, sinon False

    Raises: ValueError: si le mode de la question n'est pas géré"""

    match question.mode:
        case "qcm":
            # Pour un QCM, la bonne réponse est l'index de l'option correcte
            return user_response == question.correct_answer["index"]

        case "vrai_faux":
            # Pour un vrai/faux, la bonne réponse est un booléen
            return user_response == question.correct_answer["value"]

        case "chronologie":
            return user_response == question.correct_answer["order"]

        case "film_melange":
            return fuzzy_match(user_response, question.correct_answer["title"])

        case "citation" | "emoji" | "devinette" | "devinette_affiche" | "casting" | "blindtest":
            return fuzzy_match(user_response, question.correct_answer["film"])

        case _:
            raise ValueError(f"Mode de question inconnu : {question.mode}")


def convert_answer(mode: str, raw_value: str) -> Any:
    """Convertit la valeur texte envoyée par le joueur dans le type attendu par check_answer

    Le solo poste un formulaire, le multijoueur passe par une websocket, mais
    les deux transmettent du texte : la conversion est la même des deux côtés,
    et n'a donc pas à être réécrite dans chacun"""
    if mode == "qcm":
        return int(raw_value)
    if mode == "vrai_faux":
        return raw_value == "true"
    if mode == "chronologie":
        return raw_value.split("|")
    if mode in ("citation", "emoji", "film_melange", "devinette",
                "devinette_affiche", "casting", "blindtest"):
        return raw_value

    raise ValueError(f"Mode inconnu : {mode}")


def scramble_title(title: str, seed: Any = None) -> str:
    """Mélange les lettres d'un titre en conservant les espaces à leur place

    Un seed rend le mélange reproductible. Le multijoueur en a besoin : sans
    lui, les deux adversaires verraient deux mélanges différents du même titre,
    et l'un des deux pourrait tomber sur le plus lisible"""
    shuffler = random.Random(seed) if seed is not None else random

    letters = [char for char in title if char != " "]
    shuffler.shuffle(letters)

    scrambled = []
    letter_index = 0
    for char in title:
        if char == " ":
            scrambled.append(" ")
        else:
            scrambled.append(letters[letter_index])
            letter_index += 1

    return "".join(scrambled)