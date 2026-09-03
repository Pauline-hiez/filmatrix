"""Stockage des images uploadées sur Cloudflare R2 (API compatible S3).

Le disque du conteneur en production est éphémère : tout fichier écrit
localement (hors du dépôt git) disparaît au déploiement suivant. Les images
uploadées depuis l'admin doivent donc vivre ailleurs, sur un stockage qui
survit aux redéploiements — R2 plutôt qu'un disque persistant lié à un
hébergeur précis, pour rester indépendant de la plateforme.
"""

import os

import boto3
from botocore.config import Config


def _env(name: str) -> str:
    """Lit une variable d'environnement en retirant les espaces/retours à la
    ligne parasites qu'un copier-coller (ex. dans le dashboard Render) peut
    ajouter en fin de valeur — invisibles, mais suffisants pour faire échouer
    la signature de la requête R2 (SignatureDoesNotMatch)."""
    return os.environ[name].strip()


def _client():
    return boto3.client(
        "s3",
        endpoint_url=f"https://{_env('R2_ACCOUNT_ID')}.r2.cloudflarestorage.com",
        aws_access_key_id=_env("R2_ACCESS_KEY_ID"),
        aws_secret_access_key=_env("R2_SECRET_ACCESS_KEY"),
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


def upload_character_image(file_obj, filename: str, content_type: str | None) -> str:
    """Envoie une image de personnage vers R2 et renvoie son URL publique complète."""
    bucket = _env("R2_BUCKET_NAME")
    key = f"characters/{filename}"
    extra_args = {"ContentType": content_type} if content_type else {}
    _client().upload_fileobj(file_obj, bucket, key, ExtraArgs=extra_args)
    return f"{_env('R2_PUBLIC_URL').rstrip('/')}/{key}"
