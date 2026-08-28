"""Script d'administration : donne les droits admin à un compte déjà inscrit.

Usage : python promote_admin.py [email]

Sans argument, le script cible hiezpauline@gmail.com. La base modifiée est
celle indiquée par la variable d'environnement DATABASE_URL, ou la base
SQLite locale si cette variable n'est pas définie.
"""

import sys

from wsgi import app
from filmatrix.extensions import db
from filmatrix.models import User

DEFAULT_EMAIL = "hiezpauline@gmail.com"


def promote_to_admin(email: str) -> None:
    """Passe is_admin à True pour le compte correspondant à l'email fourni"""
    with app.app_context():
        # On n'affiche que l'hôte et le nom de la base, jamais le mot de passe
        database_uri = app.config["SQLALCHEMY_DATABASE_URI"]
        print(f"Base ciblée : {database_uri.rsplit('@', 1)[-1]}")

        user = User.query.filter_by(email=email).first()

        if user is None:
            print(f"Aucun compte trouvé pour {email}.")
            print("Inscrivez-vous d'abord sur le site, puis relancez ce script.")
            sys.exit(1)

        if user.is_admin:
            print(f"{user.username} ({email}) est déjà administrateur.")
            return

        user.is_admin = True
        db.session.commit()
        print(f"{user.username} ({email}) est maintenant administrateur.")


if __name__ == "__main__":
    promote_to_admin(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_EMAIL)
