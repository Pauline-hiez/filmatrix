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
