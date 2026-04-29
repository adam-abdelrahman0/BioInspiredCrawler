import numpy as np

from .grid import Grid
from .postprocess import flood_fill_largest
from .rules import apply_rule

CAVE_BORN = frozenset({5, 6, 7, 8})
CAVE_SURVIVE = frozenset({4, 5, 6, 7, 8})
SMOOTH_BORN = frozenset({5, 6, 7, 8})
SMOOTH_SURVIVE = frozenset({5, 6, 7, 8})


def run_ca_pipeline(
    height: int,
    width: int,
    fill_prob: float,
    ca_iterations: int,
    smooth_iterations: int,
    rng: np.random.Generator,
) -> tuple[Grid, Grid, int]:
    grid = Grid.random(height, width, fill_prob, rng)
    grid = apply_rule(grid, CAVE_BORN, CAVE_SURVIVE, ca_iterations)
    raw = grid.copy()
    grid = apply_rule(grid, SMOOTH_BORN, SMOOTH_SURVIVE, smooth_iterations)
    final, num_regions = flood_fill_largest(grid)
    return raw, final, num_regions
