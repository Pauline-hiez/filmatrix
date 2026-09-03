"""Humanise les noms des tags non-franchise encore écrits en slug.

Le sélecteur de jeu proposait « etats-unis », « annees-1980 », « tom-hanks »… :
des tags créés par import avec leur slug au lieu de leur nom lisible. Ce script
les renomme (etats-unis -> États-Unis, annees-1980 -> Années 1980,
tom-hanks -> Tom Hanks) sans toucher aux valeurs slug utilisées en interne
(tag.slug est recalculé, l'identifiant ne change pas).

Idempotent : relancer ce script ne change plus rien.

    python -m scripts.humanize_tag_slugs [--dry-run]
"""
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.exc import IntegrityError

from wsgi import app

from filmatrix.extensions import db
from filmatrix.models import Tag

SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)+$")

# Sigles et particularités qui ne suivent pas la règle « capitaliser chaque mot ».
SPECIAL = {
    "usa": "USA",
    "uk": "Royaume-Uni",
    "hbo": "HBO",
    "bbc": "BBC",
    "wwe": "WWE",
    "disney": "Disney",
}


def humanize(slug: str) -> str:
    """etats-unis -> États-Unis ; annees-1980 -> Années 1980 ; tom-hanks -> Tom Hanks."""
    words = []
    for part in slug.split("-"):
        if part in SPECIAL:
            words.append(SPECIAL[part])
        elif part.isdigit():
            words.append(part)
        else:
            words.append(part.capitalize())
    name = " ".join(words)

    # Recollages et accents usuels du catalogue (mots géographiques,
    # temporels, traits d'union des pays).
    fixes = {
        r"\bEtats Unis\b": "États-Unis",
        r"\bRoyaume Uni\b": "Royaume-Uni",
        r"\bNouvelle Zelande\b": "Nouvelle-Zélande",
        r"\bCoree Du Sud\b": "Corée du Sud",
        r"\bCoree du Sud\b": "Corée du Sud",
        r"\bScience Fiction\b": "Science-fiction",
        r"\bCinema General\b": "Cinéma général",
        r"\bAnnees\b": "Années",
        r"\bFunes\b": "Funès",
        r"\bGuillermo Del Toro\b": "Guillermo del Toro",
        r"\bM Night\b": "M. Night",
        r"\bRobert De Niro\b": "Robert De Niro",
    }
    for pattern, replacement in fixes.items():
        name = re.sub(pattern, replacement, name)
    # Particules en minuscule sauf en début de nom (déjà capitalisé).
    name = re.sub(r"(?<=\S)\s(De|Du|La|Le)\b", lambda m: " " + m.group(1).lower(), name)
    return name


def main() -> None:
    dry_run = "--dry-run" in sys.argv

    with app.app_context():
        tags = Tag.query.all()
        taken = {tag.name for tag in tags}

        renamed = 0
        for tag in tags:
            if not SLUG_RE.match(tag.name):
                continue
            new_name = humanize(tag.name)
            if new_name in taken:
                print(f"  ignoré {tag.name!r} -> {new_name!r} (collision)")
                continue

            print(f"  {tag.name!r} -> {new_name!r} [{tag.tag_type}]")
            if not dry_run:
                tag.name = new_name
                try:
                    db.session.commit()
                    taken.add(new_name)
                    renamed += 1
                except IntegrityError:
                    db.session.rollback()
                    print(f"    échec (collision UNIQUE), ignoré")

        print(f"\n{renamed} renommage(s)" + (" (dry-run, rien modifié)" if dry_run else "") + ".")


if __name__ == "__main__":
    main()
