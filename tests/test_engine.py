"""Tests du moteur de vérification des réponses (src/engine.py)"""

import pytest

from src.engine import check_answer
from src.models import Question

def make_qcm_question() -> Question:
    """Fabrique une question QCM de test, réutilisée dans plusieurs tests"""
    return Question(
        id=1,
        mode="qcm",
        category="test",
        difficulty="facile",
        prompt="Question de test",
        payload={"options": ["A", "B", "C", "D"]},
        correct_answer={"index": 2},
    )

def make_vrai_faux_question() -> Question:
    """Fabrique une question vrai/faux test"""
    return Question(
        id=2,
        mode="vrai_faux",
        category="test",
        difficulty="facile",
        prompt="Affirmation de test",
        payload={},
        correct_answer={"value": True}
        )

def test_qcm_correct_answer():
    """Une réponse QCM correcte doit renvoyer True"""
    question = make_qcm_question()
    assert check_answer(question, 2) is True

def test_qcm_wrong_answer():
    """Une réponse QCM incorrecte doit renvoyer False"""
    question = make_qcm_question()
    assert check_answer(question, 0) is False

def test_vrai_faux_correct_answer():
    """Une réponse vrai/faux correcte doit renvoyer True"""
    question = make_vrai_faux_question()
    assert check_answer(question, True) is True

def test_vrai_faux_wrong_answer():
    """Une réponse vrai/faux incorrecte doit renvoyer False"""
    question = make_vrai_faux_question()
    assert check_answer(question, False) is False

def test_unknown_mode_raises_error():
    """Un mode non géré doit lever une ValueError explicite"""
    question = make_qcm_question()
    question.mode = "mode_qui_nexiste_pas"

    with pytest.raises(ValueError):
        check_answer(question, 0)

def make_citation_question() -> Question:
    """Fabrique une question citation de test"""
    return Question(
            id=3,
            mode="citation",
            category="test",
            difficulty="moyen",
            prompt="test quote",
            payload={},
            correct_answer={"film": "Terminator"},
        )

def test_citation_correct_answer_case_insensitive():
    """Une citation correcte doit être acceptée"""
    question = make_citation_question()
    assert check_answer(question, 'terminator') is True 

def test_citation_wrong_answer():
    """Une citation incorrecte doit retourner False"""
    question = make_citation_question()
    assert check_answer(question, "Avatar") is False

def make_emoji_question() -> Question:
    """Fabrique une question emoji de test"""
    return Question(
            id=4,
            mode="emoji",
            category="test",
            difficulty="facile",
            prompt="🦁👑🌍",
            payload={},
            correct_answer={"film": "Le Roi Lion"},
        )

def test_emoji_correct_answer_case_insensitive():
    """Une réponse correcte doit être acceptée, quelle que soit la casse"""
    question = make_emoji_question()
    assert check_answer(question, "le roi lion") is True

def test_emoji_wrong_answer():
    """Une réponse incorrecte toi retourner False"""
    question = make_emoji_question()
    assert check_answer(question, "Avatar") is False 

def make_scrambled_title_question() -> Question:
    """Fabrique une question film mélangé de test"""
    return Question(
            id=5,
            mode="film_melange",
            category="test",
            difficulty="facile",
            prompt="",
            payload={},
            correct_answer={"title": "Avatar"},
        )

def test_scrambled_title_correct_answer_case_insensitive():
    """Une réponse correcte doit être acceptée quelle que soit la casse"""
    question = make_scrambled_title_question()
    assert check_answer(question, "avatar") is True 

def test_scrambled_title_wrong_answer():
    """Une réponse incorrecte doit retourner False"""
    question = make_scrambled_title_question()
    assert check_answer(question, "Titanic") is False

def make_chronology_question() -> Question:
    """Fabrique une question chronologie de test."""
    return Question(
        id=6,
        mode="chronologie",
        category="test",
        difficulty="moyen",
        prompt="",
        payload={"films": ["Avatar", "Inception", "Titanic"]},
        correct_answer={"order": ["Titanic", "Inception", "Avatar"]},
    )


def test_chronology_correct_order():
    """The correct chronological order should be accepted."""
    question = make_chronology_question()
    assert check_answer(question, ["Titanic", "Inception", "Avatar"]) is True


def test_chronology_wrong_order():
    """An incorrect order should return False."""
    question = make_chronology_question()
    assert check_answer(question, ["Avatar", "Inception", "Titanic"]) is False


def test_chronology_partial_order_wrong():
    """An order with only one swapped pair should still be rejected."""
    question = make_chronology_question()
    assert check_answer(question, ["Titanic", "Avatar", "Inception"]) is False

def make_riddle_question() -> Question:
    """Fabrique une question devinette de test"""
    return Question(
            id=7,
            mode="devinette",
            category="test",
            difficulty="moyen",
            prompt="",
            payload={"hints": ["Indice 1", "Indice 2", "Indice 3"]},
            correct_answer={"film": "Titanic"},
        )

def test_riddle_correct_answer_case_insensitive():
    """Une réponse correcte à une énigme doit être acceptée quelle que soit la casse"""
    question = make_riddle_question()
    assert check_answer(question, "titanic") is True

def test_riddle_wrong_answer():
    """Une réponse incorrecte doit retourner False"""
    question = make_riddle_question()
    assert check_answer(question, "Avatar") is False

def make_poster_riddle_question() -> Question:
    """Fabrique une question devinette-affiche de test"""
    return Question(
        id=8,
        mode="devinette_affiche",
        category="test",
        difficulty="facile",
        prompt="",
        payload={"poster_url": "https://example.com/poster.jpg"},
        correct_answer={"film": "Inception"},
        )

def test_poster_riddle_correct_answer_case_insensitive():
    """Une réponse correcte doit être acceptée quelle que soit la casse"""
    question = make_poster_riddle_question()
    assert check_answer(question, "inception") is True 

def test_poster_riddle_wrong_answer():
    """Une réponse incorrecte doit retourner False"""
    question = make_poster_riddle_question()
    assert check_answer(question, "Titanic") is False

def make_casting_question() -> Question:
    """Fabrique une question casting de test"""
    return Question(
            id=9,
            mode="casting",
            category="test",
            difficulty="moyen",
            prompt="",
            payload={"actor_photos": ["http://example.com/actor1.jpg"]},
            correct_answer={"film": "Inception"},
        )

def test_casting_correct_answer_case_insensitive():
    """Une réponse correcte doit être acceptée quelle que soit la casse"""
    question = make_casting_question()
    assert check_answer(question, "inception") is True

def test_casting_wrong_answer():
    """Une réponse incorrecte doit retourner False"""
    question = make_casting_question()
    assert check_answer(question, "Titanic") is False

def make_blindtest_question() -> Question:
    """Fabrique une question blind test de test"""
    return Question(
        id=10,
        mode="blindtest",
        category="test",
        difficulty="facile",
        prompt="",
        payload={"audio_url": "https://example.com/audio.m4a"},
        correct_answer={"film": "Le Parrain"},
        )

def test_blindtest_correct_answer_case_insensitive():
    """Une réponse correcte est acceptée, quelle que soit la casse"""
    question = make_blindtest_question()
    assert check_answer(question, "le parrain") is True

def test_blindtest_wrong_answer():
    """Une réponse incorrecte doit retourner False"""
    question = make_blindtest_question()
    assert check_answer(question, "Titanic") is False


