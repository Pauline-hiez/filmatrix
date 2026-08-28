"""Comparaison souple de réponses textuelles : accents, ponctuation, articles, fautes tolérées"""
import re 
import unicodedata

from rapidfuzz.fuzz import ratio 

ARTICLES = {"le", "la", "les", "l", "un", "une", "des", "the", "a", "an", "of", "de", "du"}

def normalize_text(text: str) -> str:
    """Normalise un texte : minuscules, sans accents, sans ponctuation, sans article"""
    text = text.lower().strip()

    text = unicodedata.normalize("NFD", text)
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")

    text = re.sub(r"[^\w\s]", " ", text)

    words = [word for word in text.split() if word not in ARTICLES]

    return " ".join(words)

def fuzzy_match(user_answer: str, correct_answer: str, threshold: int = 85) -> bool:
    """Compare deux réponses de façon souple, insensible aux fautes mineures"""
    normalize_user = normalize_text(user_answer)
    normalize_correct = normalize_text(correct_answer)

    score = ratio(normalize_user, normalize_correct)

    return score >= threshold