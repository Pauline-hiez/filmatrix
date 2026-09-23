"""Fonctions d'accès à l'API YouTube Data pour rechercher des vidéos candidates

Utilisé en repli pour le blindtest (musique introuvable sur iTunes) et pour le
mode dialogue (aucune source équivalente à iTunes n'existe pour les répliques :
YouTube est la seule source, dès le départ)."""

import os

import requests

YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"


def get_api_key() -> str:
    """Récupère la clé API YouTube depuis .env"""
    return os.environ["YOUTUBE_API_KEY"]


def search_videos(search_term: str, limit: int = 6) -> list[dict]:
    """Renvoie plusieurs vidéos candidates avec leur titre et leur chaîne.

    Contrairement à iTunes, YouTube ne fournit pas d'extrait prédécoupé :
    seul l'identifiant de la vidéo est renvoyé, le point de départ/fin de
    lecture reste à choisir en curation admin.
    """
    response = requests.get(
        YOUTUBE_SEARCH_URL,
        params={
            "key": get_api_key(),
            "q": search_term,
            "part": "snippet",
            "type": "video",
            "videoEmbeddable": "true",
            "maxResults": limit,
        },
        timeout=10,
    )
    response.raise_for_status()
    results = response.json().get("items", [])
    videos = []
    for result in results:
        video_id = result.get("id", {}).get("videoId")
        if not video_id:
            continue
        snippet = result.get("snippet", {})
        thumbnails = snippet.get("thumbnails", {})
        thumbnail = thumbnails.get("default", {}).get("url", "")
        videos.append({
            "youtube_id": video_id,
            "label": snippet.get("title") or "Vidéo YouTube",
            "channel": snippet.get("channelTitle") or "",
            "thumbnail_url": thumbnail,
        })
    return videos
