"""Tests de la validation du mot de passe"""

from src.validation import mot_de_passe_valide

def test_mot_de_passe_valide_accepte():
    assert mot_de_passe_valide("Azerty1!") is True 

def test_mot_de_passe_trop_court_refuse():
    assert mot_de_passe_valide("Az1!") is False 

def test_mot_de_passe_sans_majuscule_refuse():
    assert mot_de_passe_valide("azerty1!") is False

def test_mot_de_passe_sans_caractere_special_refuse():
    assert mot_de_passe_valide("Azerty12") is False
    