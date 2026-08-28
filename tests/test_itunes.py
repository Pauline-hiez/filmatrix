"""Test du module d'accès à itunes"""

from filmatrix.integrations.itunes import search_soundtrack_preview 

def test_search_soundtrack_finds_know_result():
    """La recherche d'une BO connue doit renvoyer une URL"""
    preview_url = search_soundtrack_preview("Le parrain Nino Rota")

    assert preview_url is not None
    assert preview_url.startswith("https://")

def test_search_soundtrack_returns_none_for_gibberish():
    """Une réponse fausse ne renvoie aucun résultat"""
    preview_url = search_soundtrack_preview("xzqwplkjqwerty12345nonexistent")

    assert preview_url is None