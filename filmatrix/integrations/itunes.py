"""Fonctions d'accès à l'API iTunes Search pour récupérer les extraits audio"""

import requests

ITUNES_SEARCH_URL = "https://itunes.apple.com/search"


def search_soundtrack_previews(search_term: str, limit: int = 6) -> list[dict]:
    """Renvoie plusieurs extraits audio exploitables avec leur titre et artiste."""
    response = requests.get(
        ITUNES_SEARCH_URL,
        params={"term": search_term, "media": "music", "limit": limit},
        timeout=10,
    )
    response.raise_for_status()
    results = response.json().get("results", [])
    previews = []
    seen_urls = set()
    for result in results:
        url = result.get("previewUrl")
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        previews.append({
            "audio_url": url,
            "label": result.get("trackName") or "Extrait audio",
            "artist": result.get("artistName") or "",
            "album": result.get("collectionName") or "",
        })
    return previews


def search_soundtrack_preview(search_term: str) -> str | None:
    """Recherche un extrait audio via l'API (compatibilité historique)."""
    previews = search_soundtrack_previews(search_term, limit=1)
    return previews[0]["audio_url"] if previews else None