from collections import deque

import numpy as np

from .grid import Grid


def _bfs_region(data: np.ndarray, visited: np.ndarray, start: tuple) -> list:
    """Return list of (r, c) coords for the connected floor region at start."""
    h, w = data.shape
    queue = deque([start])
    visited[start] = True
    cells = []
    while queue:
        r, c = queue.popleft()
        cells.append((r, c))
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nr, nc = r + dr, c + dc
            if (
                0 <= nr < h
                and 0 <= nc < w
                and not visited[nr, nc]
                and data[nr, nc] == 1
            ):
                visited[nr, nc] = True
                queue.append((nr, nc))
    return cells


def flood_fill_largest(grid: Grid) -> tuple["Grid", int]:
    """
    Keep only the largest connected floor region; fill all others with wall.
    Returns (cleaned Grid, number of disconnected regions found).
    """
    data = grid.data
    h, w = data.shape
    visited = np.zeros((h, w), dtype=bool)
    regions: list[list] = []

    for r in range(h):
        for c in range(w):
            if data[r, c] == 1 and not visited[r, c]:
                region = _bfs_region(data, visited, (r, c))
                regions.append(region)

    num_regions = len(regions)
    new_data = np.zeros((h, w), dtype=np.uint8)

    if regions:
        largest = max(regions, key=len)
        for r, c in largest:
            new_data[r, c] = 1

    return Grid(new_data), num_regions
