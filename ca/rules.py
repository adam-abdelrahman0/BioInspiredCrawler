import numpy as np

from .grid import Grid


def _step(grid: Grid, born_set: frozenset, survive_set: frozenset) -> Grid:
    """One CA generation using Moore neighborhood counts."""
    h, w = grid.height, grid.width
    counts = np.zeros((h, w), dtype=np.int8)

    # Vectorised neighbour sum via sliced additions — avoids Python hot loop.
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
    for n in born_set:
        new |= (d == 0) & (counts == n)
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
