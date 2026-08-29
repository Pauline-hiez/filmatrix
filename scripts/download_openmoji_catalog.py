"""Download the OpenMoji metadata catalog for the admin picker, enrichi des
noms et mots-clés français officiels du CLDR (Unicode Common Locale Data
Repository — les mêmes données que macOS, Android ou Windows utilisent pour
nommer les emojis en français).

OpenMoji ne fournit ses noms et mots-clés qu'en anglais : sans cet
enrichissement, chercher « château » dans le sélecteur de l'admin ne renvoie
rien, alors que « castle » fonctionne.

Run once from the project root (à relancer si le catalogue OpenMoji est mis à
jour) :
    python -m scripts.download_openmoji_catalog
"""

import json
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "static" / "assets" / "openmoji-catalog.json"
OPENMOJI_URL = "https://raw.githubusercontent.com/hfg-gmuend/openmoji/master/data/openmoji.json"
CLDR_FR_URL = (
    "https://raw.githubusercontent.com/unicode-org/cldr-json/main/cldr-json/"
    "cldr-annotations-full/annotations/fr/annotations.json"
)

# Un modificateur de teint ou de genre change le rendu de l'emoji, pas le mot
# qu'on tape pour le chercher : « main qui salue » doit rester trouvable en
# français quel que soit le teint choisi, alors que le CLDR n'annote isolément
# que la version « neutre » de la plupart des gestes.
SKIN_TONES = {"1F3FB", "1F3FC", "1F3FD", "1F3FE", "1F3FF"}
VARIATION_SELECTOR = "FE0F"


def normalize_hexcode(hexcode: str) -> str:
    """Retire les segments qui n'affectent que l'apparence, pas le sens"""
    parts = [part for part in hexcode.split("-") if part not in SKIN_TONES and part != VARIATION_SELECTOR]
    return "-".join(parts)


def build_french_index(cldr_annotations: dict) -> dict[str, dict]:
    """Construit un index hexcode normalisé -> nom et mots-clés français"""
    index: dict[str, dict] = {}
    for emoji_char, data in cldr_annotations.items():
        hexcode = normalize_hexcode("-".join(f"{ord(char):X}" for char in emoji_char))
        # Le fichier liste parfois plusieurs séquences pour un même sens (avec
        # ou sans variante de teint) : on garde la première rencontrée.
        index.setdefault(hexcode, {"name": data.get("tts", [None])[0], "tags": data.get("default", [])})
    return index


def main() -> None:
    print("Téléchargement du catalogue OpenMoji...")
    openmoji_items = requests.get(OPENMOJI_URL, timeout=60).json()

    print("Téléchargement des annotations françaises du CLDR...")
    cldr_response = requests.get(CLDR_FR_URL, timeout=60)
    cldr_response.raise_for_status()
    french_index = build_french_index(cldr_response.json()["annotations"]["annotations"])

    matched = 0
    for item in openmoji_items:
        hexcode = normalize_hexcode(item.get("hexcode", ""))
        french = french_index.get(hexcode)
        if french and french["name"]:
            item["fr_name"] = french["name"]
            item["fr_tags"] = french["tags"]
            matched += 1

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(openmoji_items, ensure_ascii=False), encoding="utf-8")
    print(f"Catalogue OpenMoji enregistré dans {OUTPUT}")
    print(f"{matched}/{len(openmoji_items)} emojis ont un nom français ; "
          f"les autres restent cherchables en anglais.")


if __name__ == "__main__":
    main()
