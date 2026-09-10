"""Tests de l'upload d'image de couverture d'album (stockage Cloudflare R2)."""

import io
from unittest.mock import patch

from filmatrix.extensions import db
from filmatrix.models import Album, User


def create_admin(username: str = "AdminAlbum", email: str = "adminalbum@filmatrix.fr") -> User:
    admin = User(username=username, email=email, is_admin=True)
    admin.set_password("Azerty1!")
    db.session.add(admin)
    db.session.commit()
    return admin


def login_admin(client, email: str = "adminalbum@filmatrix.fr") -> None:
    client.post("/connexion", data={"email": email, "password": "Azerty1!"})


def test_album_cover_image_upload_stores_r2_public_url(client, app):
    """L'image envoyée doit être confiée au stockage R2, pas écrite sur disque local."""
    with app.app_context():
        create_admin()

    login_admin(client)

    with patch(
        "filmatrix.routes.admin.upload_album_image",
        return_value="https://pub-xxxx.r2.dev/albums/fake.png",
    ) as mocked_upload:
        response = client.post(
            "/admin/albums/nouveau",
            data={
                "name": "Harry Potter",
                "sort_order": 0,
                "image_file": (io.BytesIO(b"contenu-image-factice"), "hp.png"),
            },
            content_type="multipart/form-data",
        )
    assert response.status_code == 302
    assert mocked_upload.called

    with app.app_context():
        album = Album.query.filter_by(name="Harry Potter").first()
        assert album is not None
        assert album.image_url == "https://pub-xxxx.r2.dev/albums/fake.png"


def test_album_cover_image_upload_rejects_bad_extension(client, app):
    with app.app_context():
        create_admin()

    login_admin(client)

    with patch("filmatrix.routes.admin.upload_album_image") as mocked_upload:
        response = client.post(
            "/admin/albums/nouveau",
            data={
                "name": "Album invalide",
                "sort_order": 0,
                "image_file": (io.BytesIO(b"contenu"), "malware.exe"),
            },
            content_type="multipart/form-data",
        )
    assert response.status_code == 200
    assert not mocked_upload.called

    with app.app_context():
        album = Album.query.filter_by(name="Album invalide").first()
        # Le formulaire est ré-affiché sans commit : l'album n'a jamais été créé.
        assert album is None


def test_album_cover_image_upload_surfaces_storage_failure(client, app):
    """Une erreur réseau/config côté R2 doit être signalée, pas planter en 500."""
    with app.app_context():
        create_admin()

    login_admin(client)

    with patch(
        "filmatrix.routes.admin.upload_album_image",
        side_effect=KeyError("R2_BUCKET_NAME"),
    ):
        response = client.post(
            "/admin/albums/nouveau",
            data={
                "name": "Album sans stockage",
                "sort_order": 0,
                "image_file": (io.BytesIO(b"contenu"), "ok.png"),
            },
            content_type="multipart/form-data",
        )
    assert response.status_code == 200

    with app.app_context():
        assert Album.query.filter_by(name="Album sans stockage").first() is None


def test_album_cover_crop_settings_are_persisted(client, app):
    """Les curseurs de recadrage (admin/album_form.html) doivent être
    enregistrés comme pour le cadrage des portraits de personnage."""
    with app.app_context():
        create_admin()

    login_admin(client)

    with patch(
        "filmatrix.routes.admin.upload_album_image",
        return_value="https://pub-xxxx.r2.dev/albums/fake.png",
    ):
        response = client.post(
            "/admin/albums/nouveau",
            data={
                "name": "Harry Potter",
                "sort_order": 0,
                "image_file": (io.BytesIO(b"contenu"), "hp.png"),
                "image_x": "-15",
                "image_y": "8",
                "image_scale": "125",
            },
            content_type="multipart/form-data",
        )
    assert response.status_code == 302

    with app.app_context():
        album = Album.query.filter_by(name="Harry Potter").first()
        assert album.image_x == -15
        assert album.image_y == 8
        assert album.image_scale == 125


def test_creating_an_album_without_a_cover_image_leaves_it_empty(client, app):
    """Le flux existant (aucun fichier envoyé) ne doit pas être cassé par le nouveau champ."""
    with app.app_context():
        create_admin()

    login_admin(client)

    response = client.post(
        "/admin/albums/nouveau",
        data={"name": "Album sans image", "sort_order": 0},
        content_type="multipart/form-data",
    )
    assert response.status_code == 302

    with app.app_context():
        album = Album.query.filter_by(name="Album sans image").first()
        assert album is not None
        assert album.image_url is None
