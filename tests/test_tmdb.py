"""Test du module d'accès TMDB"""

from filmatrix.integrations.tmdb import build_image_url, get_movie_cast, search_movie

def test_search_movie_finds_know_film():
    """La recherche d'un titre de film connu doit donner le résultat"""
    result = search_movie("Inception")

    assert result is not None
    assert result["title"] == "Inception"
    assert result["poster_path"] is not None

def test_search_movie_returns_none_for_gibberish():
    """La recherche d'un titre inexistant ne doit rien retourner"""
    result = search_movie("xzqwplkjqwerty12345nonexistent")

    assert result is None

def test_get_movie_cast_returns_actors():
    """La recherche d'un film connu doit retourner une liste non vide"""
    movie = search_movie("Inception")
    cast = get_movie_cast(movie["id"])

    assert len(cast) > 0
    assert "name" in cast[0]

def test_build_image_url_with_valid_path():
    """Un chemin d'image valide doit générer une URL d'image TMDB complète"""
    url = build_image_url("/example.jpg")
    assert url == "https://image.tmdb.org/t/p/w500/example.jpg"

def test_build_image_url_with_none():
    """Une image sans chemin doit retourner None"""
    url = build_image_url(None)
    assert url is None