"""Tests de la validation du mot de passe"""

from filmatrix.services.validation import is_password_valid

def test_valid_password_accepted():
    assert is_password_valid("Azerty1!") is True

def test_too_short_password_rejected():
    assert is_password_valid("Az1!") is False

def test_password_without_uppercase_rejected():
    assert is_password_valid("azerty1!") is False

def test_password_without_special_character_rejected():
    assert is_password_valid("Azerty12") is False
