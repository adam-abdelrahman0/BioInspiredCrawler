import numpy as np

from ca import Grid

from ._utils import chebyshev, is_clear_of_neighbors
from .aco import build_pheromone_map, distance_from_start


def _weighted_choice_iterative(
    cells: list[tuple[int, int]],
    weight_fn,
    rng: np.random.Generator,
    k: int,
    occupied: set[tuple[int, int]],
    min_chebyshev: int = 1,
) -> list[tuple[int, int]]:
    if len(cells) == 0 or k <= 0:
        return []

    available = list(cells)
    selected: list[tuple[int, int]] = []
    blocked = set(occupied)

    while available and len(selected) < k:
        eligible = [
            c for c in available if is_clear_of_neighbors(c, blocked, min_chebyshev)
        ]
        if not eligible:
            break

        weights = np.array(
            [max(0.0, float(weight_fn(c, selected))) for c in eligible], dtype=float
        )
        if float(weights.sum()) <= 0.0:
            weights = np.ones(len(eligible), dtype=float)

        probs = weights / weights.sum()
        pick_idx = int(rng.choice(len(eligible), p=probs))
        pick = eligible[pick_idx]

        selected.append(pick)
        blocked.add(pick)
        available.remove(pick)

    return selected


def spawn_items(
    cave: Grid,
    player: tuple[int, int],
    rng: np.random.Generator,
    coin_count: int = 10,
    food_count: int = 6,
) -> tuple[
    tuple[int, int], tuple[int, int], list[tuple[int, int]], list[tuple[int, int]]
]:
    dist = distance_from_start(cave, player)
    pheromone = build_pheromone_map(cave, player, rng)
    h, w = cave.data.shape

    floor = np.argwhere(cave.data == 1)
    floor_cells = [(int(cell[0]), int(cell[1])) for cell in floor]
    floor_cells = [c for c in floor_cells if c != player]

    def _range_cells(target: float, tol: float) -> list[tuple[int, int]]:
        low = target - tol
        high = target + tol
        return [
            c
            for c in floor_cells
            if np.isfinite(dist[c[0], c[1]]) and low <= dist[c[0], c[1]] <= high
        ]

    sword_candidates = _range_cells(13.0, 4.0)
    if not sword_candidates:
        sword_candidates = [c for c in floor_cells if np.isfinite(dist[c[0], c[1]])]

    sword_pick = _weighted_choice_iterative(
        cells=sword_candidates,
        weight_fn=lambda c, _sel: (
            (1.0 / (1.0 + abs(dist[c[0], c[1]] - 13.0))) + 0.75 * pheromone[c[0], c[1]]
        ),
        rng=rng,
        k=1,
        occupied={player},
        min_chebyshev=1,
    )
    if not sword_pick:
        raise ValueError("Not enough floor cells to place sword.")
    sword = sword_pick[0]

    shield_candidates = _range_cells(20.0, 4.0)
    if not shield_candidates:
        shield_candidates = [c for c in floor_cells if np.isfinite(dist[c[0], c[1]])]

    shield_pick = _weighted_choice_iterative(
        cells=shield_candidates,
        weight_fn=lambda c, _sel: (
            (1.0 / (1.0 + abs(dist[c[0], c[1]] - 20.0))) + 0.75 * pheromone[c[0], c[1]]
        ),
        rng=rng,
        k=1,
        occupied={player, sword},
        min_chebyshev=1,
    )
    if not shield_pick:
        raise ValueError("Not enough floor cells to place shield.")
    shield = shield_pick[0]

    occupied = {player, sword, shield}
    remaining = [c for c in floor_cells if c not in occupied]

    def coin_weight(c: tuple[int, int], selected: list[tuple[int, int]]) -> float:
        r, col = c
        edge_dist = min(r, h - 1 - r, col, w - 1 - col)
        edge_score = 1.0 / (1.0 + edge_dist)
        low_pheromone_score = 1.0 - pheromone[r, col]
        spread_bonus = 1.0
        if selected:
            dmin = min(chebyshev(c, other) for other in selected)
            spread_bonus += 0.20 * min(dmin, 8)
        return 1.5 * edge_score + 1.0 * low_pheromone_score + spread_bonus

    coins = _weighted_choice_iterative(
        cells=remaining,
        weight_fn=coin_weight,
        rng=rng,
        k=coin_count,
        occupied=occupied,
        min_chebyshev=1,
    )
    occupied.update(coins)

    remaining = [c for c in floor_cells if c not in occupied]
    finite_dist = dist[np.isfinite(dist)]
    max_dist = float(finite_dist.max()) if finite_dist.size else 1.0

    def food_weight(c: tuple[int, int], selected: list[tuple[int, int]]) -> float:
        r, col = c
        far_score = (dist[r, col] / max_dist) if np.isfinite(dist[r, col]) else 0.0
        low_pheromone_score = 1.0 - pheromone[r, col]
        spread_bonus = 1.0
        if selected:
            dmin = min(chebyshev(c, other) for other in selected)
            spread_bonus += 0.25 * min(dmin, 10)
        return 0.8 * far_score + 0.7 * low_pheromone_score + spread_bonus

    food = _weighted_choice_iterative(
        cells=remaining,
        weight_fn=food_weight,
        rng=rng,
        k=food_count,
        occupied=occupied,
        min_chebyshev=1,
    )

    return sword, shield, coins, food
