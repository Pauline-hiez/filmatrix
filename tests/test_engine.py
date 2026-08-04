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

def test_qcm_bonne_reponse():
    """Une réponse QCM correcte doit renvoyer True"""
    question = make_qcm_question()
    assert check_answer(question, 2) is True

def test_qcm_mauvaise_reponse():
    """Une réponse QCM incorrecte doit renvoyer False"""
    question = make_qcm_question()
    assert check_answer(question, 0) is False 

def test_vrai_faux_bonne_reponse():
    """Une réponse vrai/faux correcte doit renvoyer True"""
    question = make_vrai_faux_question()
    assert check_answer(question, True) is True

def test_vrai_faux_mauvaise_reponse():
    """Une réponse vrai/faux incorrecte doit renvoyer False"""
    question = make_vrai_faux_question()
    assert check_answer(question, False) is False

def test_mode_inconnu_leve_une_erreur():
    """Un mode non géré doit lever une ValueError explicite"""
    question = make_qcm_question()
    question.mode = "mode_qui_nexiste_pas"

    with pytest.raises(ValueError):
        check_answer(question, 0)