"""Test des routes Flask principales"""

def test_accueil_repond_200(client):
    """La page d'accueil doit être accessble et répondre avec succès"""
    reponse = client.get("/")
    assert reponse.status_code == 200

def test_accueil_contient_le_titre(client):
    """La page d'accueil doit contenir le nom du site"""
    reponse = client.get("/")
    assert b"Filmatrix" in reponse.data