import numpy as np

from ca import Grid

from .types import EntityPlacement

WALL = np.array([0, 0, 0], dtype=np.uint8)
FLOOR = np.array([30, 30, 30], dtype=np.uint8)
PLAYER = np.array([0, 0, 255], dtype=np.uint8)
SWORD = np.array([255, 255, 255], dtype=np.uint8)
SHIELD = np.array([128, 128, 128], dtype=np.uint8)
ENEMY = np.array([255, 0, 0], dtype=np.uint8)
COIN = np.array([255, 255, 0], dtype=np.uint8)
FOOD = np.array([139, 69, 19], dtype=np.uint8)


def render_entities_rgb(cave: Grid, entities: EntityPlacement) -> np.ndarray:
    h, w = cave.data.shape
    img = np.tile(WALL, (h, w, 1))
    img[cave.data == 1] = FLOOR

    pr, pc = entities.player
    img[pr, pc] = PLAYER

    sr, sc = entities.sword
    img[sr, sc] = SWORD

    hr, hc = entities.shield
    img[hr, hc] = SHIELD

    for r, c in entities.coins:
        img[r, c] = COIN
    for r, c in entities.food:
        img[r, c] = FOOD
    for r, c in entities.enemies:
        img[r, c] = ENEMY

    return img
