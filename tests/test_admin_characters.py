"""Tests de l'upload d'image de personnage (stockage Cloudflare R2)."""

import io
from unittest.mock import patch

from filmatrix.extensions import db
from filmatrix.models import Character, Tag, User


def create_admin(username: str = "AdminImg", email: str = "adminimg@filmatrix.fr") -> User:
    admin = User(username=username, email=email, is_admin=True)
    admin.set_password("Azerty1!")
    db.session.add(admin)
    db.session.commit()
    return admin


def create_tag(name: str = "Star Wars") -> Tag:
    tag = Tag(name=name, tag_type="univers")
    db.session.add(tag)
    db.session.commit()
    return tag


def login_admin(client, email: str = "adminimg@filmatrix.fr") -> None:
    client.post("/connexion", data={"email": email, "password": "Azerty1!"})


def test_character_image_upload_stores_r2_public_url(client, app):
    """L'image envoyée doit être confiée au stockage R2, pas écrite sur disque local."""
    with app.app_context():
        create_admin()
        tag = create_tag()
        tag_id = tag.id

    login_admin(client)

    with patch(
        "filmatrix.routes.admin.upload_character_image",
        return_value="https://pub-xxxx.r2.dev/characters/fake.png",
    ) as mocked_upload:
        response = client.post(
            "/admin/personnages/nouveau",
            data={
                "name": "Yoda",
                "tag_id": tag_id,
                "rarity": "mythique",
                "image_file": (io.BytesIO(b"contenu-image-factice"), "yoda.png"),
            },
            content_type="multipart/form-data",
        )
    assert response.status_code == 302
    assert mocked_upload.called

    with app.app_context():
        character = Character.query.filter_by(name="Yoda").first()
        assert character is not None
        assert character.image_url == "https://pub-xxxx.r2.dev/characters/fake.png"


def test_character_image_upload_rejects_bad_extension(client, app):
    with app.app_context():
        create_admin()
        tag = create_tag()
        tag_id = tag.id

    login_admin(client)

    with patch("filmatrix.routes.admin.upload_character_image") as mocked_upload:
        response = client.post(
            "/admin/personnages/nouveau",
            data={
                "name": "Personnage invalide",
                "tag_id": tag_id,
                "rarity": "commun",
                "image_file": (io.BytesIO(b"contenu"), "malware.exe"),
            },
            content_type="multipart/form-data",
        )
    assert response.status_code == 200
    assert not mocked_upload.called

    with app.app_context():
        assert Character.query.filter_by(name="Personnage invalide").first() is None


def test_character_image_upload_surfaces_storage_failure(client, app):
    """Une erreur réseau/config côté R2 doit être signalée, pas planter en 500."""
    with app.app_context():
        create_admin()
        tag = create_tag()
        tag_id = tag.id

    login_admin(client)

    with patch(
        "filmatrix.routes.admin.upload_character_image",
        side_effect=KeyError("R2_BUCKET_NAME"),
    ):
        response = client.post(
            "/admin/personnages/nouveau",
            data={
                "name": "Personnage sans stockage",
                "tag_id": tag_id,
                "rarity": "commun",
                "image_file": (io.BytesIO(b"contenu"), "ok.png"),
            },
            content_type="multipart/form-data",
        )
    assert response.status_code == 200

    with app.app_context():
        assert Character.query.filter_by(name="Personnage sans stockage").first() is None
