TILE_SIZE = 32
MAP_WIDTH = 80
MAP_HEIGHT = 50
VIEW_TILES = 10
VIEWPORT_WIDTH = VIEW_TILES * TILE_SIZE
VIEWPORT_HEIGHT = VIEW_TILES * TILE_SIZE
HUD_HEIGHT = 150
WINDOW_PADDING = 20

INITIAL_HEARTS = 3
MAX_HEARTS = 5
COIN_COUNT = 10
FOOD_COUNT = 6
ENEMY_COUNT = 20
ENEMY_MOVE_MS = 220
LEVEL_COMPLETE_MS = 1500
TARGET_FPS = 60
FRAME_MS = int(1000 / TARGET_FPS)

BG = "#0b1015"
PANEL = "#151b22"
PANEL_EDGE = "#334052"
TEXT = "#ecf2f9"
TEXT_MUTED = "#9ba5b1"
GOLD = "#e0b84d"
HEART = "#d85d74"
FLOOR_A = "#48515a"
FLOOR_B = "#414951"
WALL_A = "#20252c"
WALL_B = "#2b3139"
WALL_C = "#161b21"
SHADOW = "#0a0d11"

ITEM_SWORD = "sword"
ITEM_SHIELD = "shield"
ITEM_FOOD = "food"
ITEM_COIN = "coin"

DIRECTIONS: dict[str, tuple[int, int]] = {
    "up": (-1, 0),
    "down": (1, 0),
    "left": (0, -1),
    "right": (0, 1),
}
MOVE_KEYS: dict[str, str] = {
    "Up": "up",
    "Down": "down",
    "Left": "left",
    "Right": "right",
}
ATTACK_KEYS: set[str] = {"space"}
