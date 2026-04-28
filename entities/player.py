import numpy as np

from ca import Grid


def spawn_player(cave: Grid, rng: np.random.Generator) -> tuple[int, int]:
    floor_cells = np.argwhere(cave.data == 1)
    if floor_cells.size == 0:
        raise ValueError("Cannot spawn player: cave has no floor cells.")
    idx = int(rng.integers(0, len(floor_cells)))
    r, c = floor_cells[idx]
    return int(r), int(c)
