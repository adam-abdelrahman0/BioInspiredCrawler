import numpy as np

from .grid import Grid


def _step(grid: Grid, born_set: frozenset, survive_set: frozenset) -> Grid:
    h, w = grid.height, grid.width
    counts = np.zeros((h, w), dtype=np.int8)

    # Vectorised neighbour sum via sliced additions 
    # avoids Python hot loop
    d = grid.data
    counts[1:, :] += d[:-1, :]  # north
    counts[:-1, :] += d[1:, :]  # south
    counts[:, 1:] += d[:, :-1]  # west
    counts[:, :-1] += d[:, 1:]  # east
    counts[1:, 1:] += d[:-1, :-1]  # NW
    counts[1:, :-1] += d[:-1, 1:]  # NE
    counts[:-1, 1:] += d[1:, :-1]  # SW
    counts[:-1, :-1] += d[1:, 1:]  # SE

    new = np.zeros((h, w), dtype=np.uint8)

    # 'which wall cells have {n} floor neighbors?'
    # those cells turn into floors
    # iterates from 5 to 8
    for n in born_set:
        new |= (d == 0) & (counts == n)
    
    # similar idea for survive set (4 through 8)
    # loops through each floor cell and if it has exactly n floor neighbors, keep it
    for n in survive_set:
        new |= (d == 1) & (counts == n)

    return Grid(new)


def apply_rule(
    grid: Grid,
    born_set: frozenset,
    survive_set: frozenset,
    iterations: int,
) -> Grid:
    for _ in range(iterations):
        grid = _step(grid, born_set, survive_set)
    return grid
