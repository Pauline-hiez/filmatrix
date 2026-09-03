"""Calcule de la grille de révélation puzzle pour un personnage en cours de déblocage"""

import random

GRID_SIZE = 9

def get_puzzle_grid(character_id: int, fragments: int, fragments_required: int) -> list[bool]:
    """Renvoie une grille de 9 cases, inquiquant lesquelles sont révélées"""

    if fragments_required <= 0:
        return [True] * GRID_SIZE

    progress_ratio = min(fragments / fragments_required, 1.0)
    revealed_count = round(progress_ratio * GRID_SIZE)

    cell_order = list(range(GRID_SIZE))
    shuffler = random.Random(character_id)
    shuffler.shuffle(cell_order)

    revealed_cells = set(cell_order[:revealed_count])

    return [index in revealed_cells for index in range(GRID_SIZE)]


def get_puzzle_last_cell(character_id: int, fragments: int, fragments_required: int) -> int | None:
    """Renvoie l'index de la case révélée au tout dernier fragment.

    Sert à animer la case qui vient d'apparaître sur la grille (micro-
    animation côté client). Renvoie None si rien de nouveau (0 fragment,
    grille déjà pleine, ou seuil non franchi).
    """
    if fragments_required <= 0:
        return None

    previous_count = round(min(max(fragments - 1, 0) / fragments_required, 1.0) * GRID_SIZE)
    current_count = round(min(fragments / fragments_required, 1.0) * GRID_SIZE)
    if current_count <= previous_count:
        return None

    cell_order = list(range(GRID_SIZE))
    shuffler = random.Random(character_id)
    shuffler.shuffle(cell_order)
    # La nouvelle case est la dernière entrée de l'ordre qui n'était pas encore
    # révélée : c'est l'index (current_count - 1) dans l'ordre mélangé.
    return cell_order[current_count - 1]
