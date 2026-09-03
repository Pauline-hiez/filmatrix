"""Aligne fragments_required des personnages existants sur leur rareté.

Le formulaire d'admin applique désormais automatiquement le barème
RARITY_FRAGMENT_COSTS (catalog_rarities.py) à la création comme à la
modification. Ce script rattrape les personnages créés avant ce changement.

Par défaut, mode « observation » : rien n'est modifié, seuls les écarts sont
listés. Ajouter --apply pour mettre la base à jour.

--skip-unlocked exclut les personnages déjà débloqués par au moins un joueur :
leur progression est visible en jeu, changer le nombre de fragments requis à
postériori serait déroutant.

Usage :
    python -m scripts.sync_fragments_required            # liste les écarts
    python -m scripts.sync_fragments_required --apply    # applique le barème
    python -m scripts.sync_fragments_required --apply --skip-unlocked
"""

import sys

from filmatrix import create_app
from filmatrix.catalog_rarities import fragments_for_rarity
from filmatrix.extensions import db
from filmatrix.models import Character, UserCharacter


def main() -> int:
    apply_changes = "--apply" in sys.argv
    skip_unlocked = "--skip-unlocked" in sys.argv

    app = create_app()
    with app.app_context():
        characters = Character.query.order_by(Character.rarity, Character.name).all()

        unlocked_character_ids: set[int] = set()
        if skip_unlocked:
            unlocked_character_ids = {
                row.character_id
                for row in UserCharacter.query.with_entities(
                    UserCharacter.character_id
                )
                .filter(UserCharacter.unlocked_at.isnot(None))
                .all()
            }

        mismatches = []
        for character in characters:
            target = fragments_for_rarity(character.rarity)
            if character.fragments_required == target:
                continue
            if skip_unlocked and character.id in unlocked_character_ids:
                continue
            mismatches.append((character, target))

        if not mismatches:
            print("Tous les personnages sont déjà alignés sur le barème.")
            return 0

        print(f"{len(mismatches)} personnage(s) à ajuster :\n")
        for character, target in mismatches:
            print(
                f"  - {character.name} [{character.rarity}] : "
                f"{character.fragments_required} -> {target}"
            )

        if not apply_changes:
            print(
                "\nMode observation : rien n'a été modifié. "
                "Relancez avec --apply pour appliquer."
            )
            return 0

        for character, target in mismatches:
            character.fragments_required = target
        db.session.commit()
        print(f"\n{len(mismatches)} personnage(s) mis à jour.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
