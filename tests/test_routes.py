"""Test des routes Flask principales"""

def test_accueil_repond_200(client):
    """La page d'accueil doit être accessble et répondre avec succès"""
    reponse = client.get("/")
    assert reponse.status_code == 200

def test_accueil_contient_le_titre(client):
    """La page d'accueil doit contenir le nom du site"""
    reponse = client.get("/")
    assert b"Filmatrix" in reponse.data

def test_inscription_cree_un_compte(client):
    """Une inscription avec des données valides doit créer un compte et rediriger"""
    reponse = client.post(
            "/inscription",
            data ={
                "username": "TestUser",
                "email": "test@filmatrix.fr",
                "password": "Azerty1!",
                },
                follow_redirects=True,
        )

    assert reponse.status_code == 200
    assert b"Se connecter" in reponse.data

def test_inscription_refuse_mot_de_passe_invalide(client):
    """Une inscription avec un mot de passe trop faible doit être refusée"""
    reponse = client.post(
            "/inscription",
            data={
                "username": "TestUser2",
                "email": "test2@filmatrix.fr",
                "password": "faible",
                },
        )
    assert b"ne respecte pas les r" in reponse.data