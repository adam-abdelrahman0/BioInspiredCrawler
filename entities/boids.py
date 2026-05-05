"""
Boids (Reynolds 1987) flocking simulation for swarm enemy behavior.

Each agent applies three steering forces every tick:
  - Separation  : repel from boids within SEPARATION_RADIUS
  - Alignment   : match average velocity of boids within ALIGNMENT_RADIUS
  - Cohesion    : steer toward center-of-mass of boids within COHESION_RADIUS

Plus a seek force that pulls the swarm toward the player when within SEEK_RADIUS.

The continuous velocity vector is computed per-agent, then projected onto the
discrete tile grid by scoring each walkable neighbor with the dot product against
the desired direction and moving to the best available tile.
"""

from collections import deque

import numpy as np

from ca import Grid

SEPARATION_RADIUS = 2.5
ALIGNMENT_RADIUS = 5.0
COHESION_RADIUS = 7.0
SEEK_RADIUS = 15.0

W_SEPARATION = 1.8
W_ALIGNMENT = 0.6
W_COHESION = 0.8
W_SEEK = 1.2

MAX_SPEED = 1.5

_CARDINALS = ((-1, 0), (1, 0), (0, -1), (0, 1))


def boids_step(
    positions: np.ndarray,
    velocities: np.ndarray,
    alive: np.ndarray,
    player_pos: tuple[int, int],
    cave: Grid,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Advance all boid agents one discrete step.

    Args:
        positions:  (N, 2) float array of current (row, col) positions.
        velocities: (N, 2) float array of current velocity vectors.
        alive:      (N,)   bool array; dead agents are skipped entirely.
        player_pos: (row, col) of the player for the seek force.
        cave:       Grid used for walkability checks.
        rng:        RNG for tiebreaking equal-score moves.

    Returns:
        (new_positions, new_velocities, from_positions) — all (N, 2) arrays.
        from_positions is the position before movement, used for interpolation.
    """
    h, w = cave.data.shape
    n = len(positions)
    from_positions = positions.copy()
    new_positions = positions.copy()
    new_velocities = velocities.copy()
    player = np.array(player_pos, dtype=float)

    claimed: set[tuple[int, int]] = set()

    for i in range(n):
        if not alive[i]:
            continue

        pos = positions[i].astype(float)
        vel = velocities[i].copy()

        sep = np.zeros(2)
        align = np.zeros(2)
        cohesion_sum = np.zeros(2)
        sep_n = align_n = cohesion_n = 0

        for j in range(n):
            if i == j or not alive[j]:
                continue
            other = positions[j].astype(float)
            diff = pos - other
            dist = float(np.linalg.norm(diff))

            if 0 < dist < SEPARATION_RADIUS:
                sep += diff / dist
                sep_n += 1
            if dist < ALIGNMENT_RADIUS:
                align += velocities[j]
                align_n += 1
            if dist < COHESION_RADIUS:
                cohesion_sum += other
                cohesion_n += 1

        sep_force = sep / sep_n if sep_n else sep

        if align_n:
            align /= align_n
            norm = float(np.linalg.norm(align))
            align_force = align / norm if norm > 0 else align
        else:
            align_force = align

        if cohesion_n:
            toward = cohesion_sum / cohesion_n - pos
            norm = float(np.linalg.norm(toward))
            cohesion_force = toward / norm if norm > 0 else toward
        else:
            cohesion_force = np.zeros(2)

        to_player = player - pos
        dist_to_player = float(np.linalg.norm(to_player))
        if 0 < dist_to_player < SEEK_RADIUS:
            seek_force = to_player / dist_to_player
        else:
            seek_force = np.zeros(2)

        desired = (
            W_SEPARATION * sep_force
            + W_ALIGNMENT * align_force
            + W_COHESION * cohesion_force
            + W_SEEK * seek_force
        )

        vel = vel + desired
        speed = float(np.linalg.norm(vel))
        if speed > MAX_SPEED:
            vel = vel / speed * MAX_SPEED
        new_velocities[i] = vel

        r0, c0 = int(positions[i, 0]), int(positions[i, 1])
        neighbors = [
            (r0 + dr, c0 + dc)
            for dr, dc in _CARDINALS
            if 0 <= r0 + dr < h
            and 0 <= c0 + dc < w
            and cave.data[r0 + dr, c0 + dc] == 1
        ]

        if neighbors:
            scores = [vel[0] * (nr - r0) + vel[1] * (nc - c0) for nr, nc in neighbors]
            best_score = max(scores)
            best = [nb for nb, s in zip(neighbors, scores) if s >= best_score - 0.01]
            unclaimed = [nb for nb in best if nb not in claimed]
            pick = (
                unclaimed[int(rng.integers(0, len(unclaimed)))]
                if unclaimed
                else (r0, c0)
            )
        else:
            pick = (r0, c0)

        claimed.add(pick)
        new_positions[i] = np.array(pick, dtype=float)

    return new_positions, new_velocities, from_positions


def spawn_boid_swarm(
    cave: Grid,
    center: tuple[int, int],
    blocked: set[tuple[int, int]],
    rng: np.random.Generator,
    count: int = 8,
) -> list[tuple[int, int]]:
    """
    Spawn a spatially clustered group of boid agents near center.

    BFS-expands from center to gather a local pool of floor tiles, then
    samples count positions from that pool. Passing the exit tile as center
    places the swarm there so they guard the exit rather than roaming randomly.
    """
    queue: deque[tuple[int, int]] = deque([center])
    visited: set[tuple[int, int]] = {center}
    nearby: list[tuple[int, int]] = [center]
    target_pool = count * 4

    while queue and len(nearby) < target_pool:
        r, c = queue.popleft()
        for dr, dc in _CARDINALS:
            nr, nc = r + dr, c + dc
            if (
                (nr, nc) not in visited
                and 0 <= nr < cave.height
                and 0 <= nc < cave.width
                and cave.data[nr, nc] == 1
            ):
                visited.add((nr, nc))
                queue.append((nr, nc))
                nearby.append((nr, nc))

    eligible = [cell for cell in nearby if cell not in blocked]
    if not eligible:
        return []

    k = min(count, len(eligible))
    indices = rng.choice(len(eligible), size=k, replace=False)
    return [eligible[int(i)] for i in indices]
