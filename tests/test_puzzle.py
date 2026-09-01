"""Tests du calcul de la grille de révélation puzzle."""

from filmatrix.services.puzzle import GRID_SIZE, get_puzzle_grid


def test_no_fragments_reveals_nothing():
    """Si pas de fragment, aucune cellule ne doit se révéler"""
    grid = get_puzzle_grid(character_id=1, fragments=0, fragments_required=9)
    assert all(cell is False for cell in grid)


def test_full_fragments_reveals_everything():
    """Une fois tous les fragments collectés, chaque cellule doit se révéler"""
    grid = get_puzzle_grid(character_id=1, fragments=9, fragments_required=9)
    assert all(cell is True for cell in grid)


def test_partial_fragments_reveals_proportional_cells():
    """La moitié des fragments doit révéler approximativement la moitié de la grille"""
    grid = get_puzzle_grid(character_id=1, fragments=4, fragments_required=8)
    revealed_count = sum(1 for cell in grid if cell)
    assert revealed_count == 4


def test_grid_is_stable_for_same_character(app):
    """L'ordre de révélation doit être identique pour tous les appels concernant le même personnage"""
    grid_first_call = get_puzzle_grid(character_id=42, fragments=3, fragments_required=9)
    grid_second_call = get_puzzle_grid(character_id=42, fragments=3, fragments_required=9)
    assert grid_first_call == grid_second_call


def test_grid_differs_between_characters():
    """Les différents personnages ne doivent pas apparaître exactement dans le même ordre"""
    grid_character_a = get_puzzle_grid(character_id=1, fragments=3, fragments_required=9)
    grid_character_b = get_puzzle_grid(character_id=2, fragments=3, fragments_required=9)
    assert grid_character_a != grid_character_b


def test_revealed_cells_stay_revealed_as_fragments_increase():
    """Une cellule révélée à N fragments devrait rester révélée à N+1 fragments"""
    grid_at_three = get_puzzle_grid(character_id=7, fragments=3, fragments_required=9)
    grid_at_four = get_puzzle_grid(character_id=7, fragments=4, fragments_required=9)

    for index in range(GRID_SIZE):
        if grid_at_three[index]:
            assert grid_at_four[index] is True