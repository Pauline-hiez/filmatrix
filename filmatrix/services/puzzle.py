"""Calcule de la grille de révélation puzzle pour un personnage en cours de déblocage"""

import math
import random

# Plafond de cases : au-delà, la grille deviendrait illisible sur une carte
# aussi petite. En pratique aucune rareté ne dépasse ce nombre de fragments
# (voir RARITY_FRAGMENT_COSTS dans catalog_rarities.py) : le plafond ne joue
# donc que pour une valeur personnalisée inhabituelle côté admin.
MAX_GRID_SIZE = 9


def grid_size_for(fragments_required: int) -> int:
    """Nombre de cases de la grille pour ce personnage.

    Une case par fragment à gagner (plafonné à MAX_GRID_SIZE) : la grille
    colle ainsi au vrai nombre de fragments requis — 3 cases pour un commun,
    8 pour un légendaire — au lieu d'un 3x3 fixe qui ne représentait rien
    pour ces raretés."""
    return max(1, min(fragments_required, MAX_GRID_SIZE))


def puzzle_columns(grid_size: int) -> int:
    """Nombre de colonnes pour afficher ``grid_size`` cases en grille la
    plus carrée possible (3 cases -> 2x2, 9 cases -> 3x3...)."""
    return max(1, math.ceil(math.sqrt(grid_size)))


def get_puzzle_grid(character_id: int, fragments: int, fragments_required: int) -> list[bool]:
    """Renvoie la grille de révélation, indiquant quelles cases sont révélées"""

    if fragments_required <= 0:
        return [True] * MAX_GRID_SIZE

    grid_size = grid_size_for(fragments_required)
    progress_ratio = min(fragments / fragments_required, 1.0)
    revealed_count = round(progress_ratio * grid_size)

    cell_order = list(range(grid_size))
    shuffler = random.Random(character_id)
    shuffler.shuffle(cell_order)

    revealed_cells = set(cell_order[:revealed_count])

    return [index in revealed_cells for index in range(grid_size)]


def get_puzzle_last_cell(character_id: int, fragments: int, fragments_required: int) -> int | None:
    """Renvoie l'index de la case révélée au tout dernier fragment.

    Sert à animer la case qui vient d'apparaître sur la grille (micro-
    animation côté client). Renvoie None si rien de nouveau (0 fragment,
    grille déjà pleine, ou seuil non franchi).
    """
    if fragments_required <= 0:
        return None

    grid_size = grid_size_for(fragments_required)
    previous_count = round(min(max(fragments - 1, 0) / fragments_required, 1.0) * grid_size)
    current_count = round(min(fragments / fragments_required, 1.0) * grid_size)
    if current_count <= previous_count:
        return None

    cell_order = list(range(grid_size))
    shuffler = random.Random(character_id)
    shuffler.shuffle(cell_order)
    # La nouvelle case est la dernière entrée de l'ordre qui n'était pas encore
    # révélée : c'est l'index (current_count - 1) dans l'ordre mélangé.
    return cell_order[current_count - 1]
