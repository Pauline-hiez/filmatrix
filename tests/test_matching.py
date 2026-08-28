"""Tests de la comparaison souple de réponses"""

from src.matching import fuzzy_match, normalize_text


def test_normalize_removes_accents():
    """Les accents doivent être retirés lors de la normalisation"""
    assert normalize_text("Napoléon") == "napoleon"


def test_normalize_removes_punctuation():
    """La ponctuation doit être remplacée par des espaces, pas simplement retirée"""
    assert normalize_text("Spider-Man") == "spider man"


def test_normalize_removes_articles():
    """Les articles courants doivent être retirés"""
    assert normalize_text("Le Roi Lion") == "roi lion"
    assert normalize_text("The Godfather") == "godfather"


def test_fuzzy_match_accepts_exact_match():
    """Une correspondance exacte (après normalisation) doit être acceptée"""
    assert fuzzy_match("Napoléon Bonaparte", "Napoléon Bonaparte") is True


def test_fuzzy_match_accepts_minor_typo():
    """Une petite faute de frappe doit quand même être acceptée"""
    assert fuzzy_match("Napoleon Bonapart", "Napoléon Bonaparte") is True


def test_fuzzy_match_accepts_missing_accent():
    """Un accent manquant ne doit pas empêcher la correspondance"""
    assert fuzzy_match("napoleon bonaparte", "Napoléon Bonaparte") is True


def test_fuzzy_match_accepts_article_difference():
    """La présence ou l'absence d'un article ne doit pas empêcher la correspondance"""
    assert fuzzy_match("Roi Lion", "Le Roi Lion") is True


def test_fuzzy_match_rejects_different_answer():
    """Une réponse complètement différente doit être refusée"""
    assert fuzzy_match("Louis XIV", "Napoléon Bonaparte") is False


def test_fuzzy_match_rejects_too_many_typos():
    """Trop de différences doivent quand même être refusées"""
    assert fuzzy_match("xyz totally wrong", "Napoléon Bonaparte") is False