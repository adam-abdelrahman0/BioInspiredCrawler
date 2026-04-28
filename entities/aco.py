from collections import deque

import numpy as np

from ca import Grid


def distance_from_start(cave: Grid, start: tuple[int, int]) -> np.ndarray:
    h, w = cave.data.shape
    dist = np.full((h, w), np.inf, dtype=float)
    sr, sc = start
    if cave.data[sr, sc] != 1:
        return dist

    queue = deque([(sr, sc)])
    dist[sr, sc] = 0.0
    while queue:
        r, c = queue.popleft()
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nr, nc = r + dr, c + dc
            if (
                0 <= nr < h
                and 0 <= nc < w
                and cave.data[nr, nc] == 1
                and np.isinf(dist[nr, nc])
            ):
                dist[nr, nc] = dist[r, c] + 1.0
                queue.append((nr, nc))
    return dist


def build_pheromone_map(
    cave: Grid,
    start: tuple[int, int],
    rng: np.random.Generator,
    ants: int = 150,
    steps: int = 80,
    evaporation: float = 0.02,
    deposit: float = 1.0,
) -> np.ndarray:
    h, w = cave.data.shape
    pheromone = np.zeros((h, w), dtype=float)
    sr, sc = start

    for _ in range(ants):
        r, c = sr, sc
        pheromone[r, c] += deposit
        for _ in range(steps):
            neighbors = []
            for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                nr, nc = r + dr, c + dc
                if 0 <= nr < h and 0 <= nc < w and cave.data[nr, nc] == 1:
                    neighbors.append((nr, nc))

            if not neighbors:
                break

            weights = np.array(
                [pheromone[nr, nc] + 1.0 for nr, nc in neighbors], dtype=float
            )
            weights /= weights.sum()
            next_idx = int(rng.choice(len(neighbors), p=weights))
            r, c = neighbors[next_idx]
            pheromone[r, c] += deposit

        pheromone *= 1.0 - evaporation

    if pheromone.max() > 0:
        pheromone /= pheromone.max()
    return pheromone
