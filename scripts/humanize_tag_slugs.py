"""Humanise les noms des tags non-franchise encore écrits en slug.

Le sélecteur de jeu proposait « etats-unis », « annees-1980 », « tom-hanks »… :
des tags créés par import avec leur slug au lieu de leur nom lisible. Ce script
corrige la valeur stockée en base (etats-unis -> États-Unis, tom-hanks ->
Tom Hanks), pour de bon plutôt qu'à chaque affichage.

Depuis, l'affichage lui-même passe aussi par la même humanisation
(filmatrix.catalog_rarities.humanize_tag_name, appliquée en direct par les
gabarits joueur) : ce script reste utile pour nettoyer les valeurs stockées
(admin, exports...), mais n'est plus la seule protection contre un slug
affiché tel quel — y compris sur un environnement où il n'aurait jamais
tourné (ex. la base de production).

Idempotent : relancer ce script ne change plus rien.

    python -m scripts.humanize_tag_slugs [--dry-run]
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.exc import IntegrityError

from wsgi import app

from filmatrix.catalog_rarities import humanize_tag_name
from filmatrix.extensions import db
from filmatrix.models import Tag

SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)+$")


def main() -> None:
    dry_run = "--dry-run" in sys.argv

    with app.app_context():
        tags = Tag.query.all()
        taken = {tag.name for tag in tags}

        renamed = 0
        for tag in tags:
            if not SLUG_RE.match(tag.name):
                continue
            new_name = humanize_tag_name(tag.name)
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
