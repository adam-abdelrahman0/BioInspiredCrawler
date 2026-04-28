import numpy as np

from ca import Grid

from .aco import build_pheromone_map, distance_from_start


def _chebyshev(a: tuple[int, int], b: tuple[int, int]) -> int:
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def _is_clear_of_neighbors(
    cell: tuple[int, int], occupied: set[tuple[int, int]], min_chebyshev: int = 1
) -> bool:
    for other in occupied:
        if _chebyshev(cell, other) <= min_chebyshev:
            return False
    return True


def spawn_enemies(
    cave: Grid,
    player: tuple[int, int],
    blocked: set[tuple[int, int]],
    coin_positions: list[tuple[int, int]],
    rng: np.random.Generator,
    enemy_count: int = 20,
) -> list[tuple[int, int]]:
    pheromone = build_pheromone_map(cave, player, rng, ants=220, steps=140)
    dist_from_start = distance_from_start(cave, player)

    floor = np.argwhere(cave.data == 1)
    candidates = [
        (int(cell[0]), int(cell[1]))
        for cell in floor
        if (int(cell[0]), int(cell[1])) not in blocked
    ]

    if len(candidates) == 0:
        return []

    finite = dist_from_start[np.isfinite(dist_from_start)]
    max_dist = float(finite.max()) if finite.size else 1.0

    selected: list[tuple[int, int]] = []
    occupied = set(blocked)
    count = min(enemy_count, len(candidates))

    while len(selected) < count:
        eligible = [
            c
            for c in candidates
            if c not in occupied and _is_clear_of_neighbors(c, occupied, 1)
        ]
        if not eligible:
            break

        weights = []
        for r, c in eligible:
            near_coin = 0.0
            if coin_positions:
                d_coin = min(_chebyshev((r, c), coin) for coin in coin_positions)
                near_coin = 1.0 / (1.0 + d_coin)

            far_from_start = (
                (dist_from_start[r, c] / max_dist)
                if np.isfinite(dist_from_start[r, c])
                else 0.0
            )
            low_pheromone = 1.0 - pheromone[r, c]

            spread_bonus = 1.0
            if selected:
                d_enemy = min(_chebyshev((r, c), e) for e in selected)
                spread_bonus += 0.30 * min(d_enemy, 12)

            w = (
                1.2 * near_coin
                + 0.8 * far_from_start
                + 0.8 * low_pheromone
                + spread_bonus
            )
            weights.append(max(0.0, w))

        weights_arr = np.array(weights, dtype=float)
        if float(weights_arr.sum()) <= 0.0:
            weights_arr = np.ones(len(eligible), dtype=float)

        probs = weights_arr / weights_arr.sum()
        pick = eligible[int(rng.choice(len(eligible), p=probs))]
        selected.append(pick)
        occupied.add(pick)

    return selected
