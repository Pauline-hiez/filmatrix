"""Script de deploiement : met le schema de la base au niveau du code avant le seed"""

from flask_migrate import stamp, upgrade
from sqlalchemy import inspect

from app import app
from src.database import db


def prepare_db() -> None:
    """Applique les migrations sur une base existante, cree le schema sur une base vierge"""
    with app.app_context():
        base_vierge = not inspect(db.engine).has_table("alembic_version")

        if base_vierge:
            # Aucune migration ne cree les tables de depart : sur une base neuve
            # le schema vient des modeles, et on note qu'il est deja a jour.
            db.create_all()
            stamp()
            print("Base vierge : schema cree depuis les modeles.")
        else:
            # Base existante : seules les migrations peuvent ajouter les colonnes
            # manquantes, db.create_all() ne touche pas aux tables deja creees.
            upgrade()
            db.create_all()
            print("Base existante : migrations appliquees.")


if __name__ == "__main__":
    prepare_db()
