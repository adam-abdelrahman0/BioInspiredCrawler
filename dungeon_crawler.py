import math
import tkinter as tk
from dataclasses import dataclass

import numpy as np
import yaml

from ca import Grid, apply_rule, flood_fill_largest
from entities import spawn_enemies, spawn_items, spawn_player
from entities.aco import distance_from_start


# Map size, window sizing, pacing, colors, and item identifiers used throughout the game.
TILE_SIZE = 32
MAP_WIDTH = 80
MAP_HEIGHT = 50
VIEW_TILES = 10
VIEWPORT_WIDTH = VIEW_TILES * TILE_SIZE
VIEWPORT_HEIGHT = VIEW_TILES * TILE_SIZE
HUD_HEIGHT = 150
WINDOW_PADDING = 20

CAVE_BORN = frozenset({5, 6, 7, 8})
CAVE_SURVIVE = frozenset({4, 5, 6, 7, 8})
SMOOTH_BORN = frozenset({5, 6, 7, 8})
SMOOTH_SURVIVE = frozenset({5, 6, 7, 8})

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
EMPTY = "#39414a"
FLOOR_A = "#48515a"
FLOOR_B = "#414951"
WALL_A = "#20252c"
WALL_B = "#2b3139"
WALL_C = "#161b21"
GREEN = "#67da86"
SHADOW = "#0a0d11"

ITEM_SWORD = "sword"
ITEM_SHIELD = "shield"
ITEM_FOOD = "food"
ITEM_COIN = "coin"

DIRECTIONS = {
    "up": (-1, 0),
    "down": (1, 0),
    "left": (0, -1),
    "right": (0, 1),
}
MOVE_KEYS = {
    "Up": "up",
    "Down": "down",
    "Left": "left",
    "Right": "right",
}
ATTACK_KEYS = {"space"}


# Patrol behavior and interpolated render state for each enemy.
@dataclass
class Enemy:
    row: int
    col: int
    origin_row: int
    origin_col: int
    axis: str
    radius: int
    direction: int
    alive: bool = True
    render_row: float = 0.0
    render_col: float = 0.0
    from_row: int = 0
    from_col: int = 0


# Player grid position and current facing direction.
@dataclass
class Player:
    row: int
    col: int
    facing: str = "down"


# Pickup type and tile location on the map.
@dataclass
class Item:
    kind: str
    row: int
    col: int


# Tk window, game state, update loop, rendering, and level lifecycle.
class DungeonCrawlerGame:
    # Creates the window, sizes the viewport to the display, and prepares persistent run state.
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Dungeon Crawler")
        self.root.resizable(False, False)
        self.root.configure(bg=BG)
        self.root.update_idletasks()

        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        horizontal_scale = max(1.0, (screen_width - (WINDOW_PADDING * 2)) / VIEWPORT_WIDTH)
        vertical_scale = max(1.0, (screen_height - HUD_HEIGHT - 160) / VIEWPORT_HEIGHT)
        self.render_scale = min(horizontal_scale, vertical_scale)
        self.window_width = int(VIEWPORT_WIDTH * self.render_scale) + (WINDOW_PADDING * 2)
        self.viewport_width = self.window_width - (WINDOW_PADDING * 2)
        self.viewport_height = int(VIEWPORT_HEIGHT * self.render_scale)
        self.window_height = HUD_HEIGHT + self.viewport_height
        self.world_left = WINDOW_PADDING

        self.canvas = tk.Canvas(
            self.root,
            width=self.window_width,
            height=self.window_height,
            bg=BG,
            bd=0,
            highlightthickness=0,
        )
        self.canvas.pack()

        self.root.bind("<KeyPress>", self.on_key_press)
        self.canvas.bind("<Button-1>", self.on_click)

        self.cfg = self.load_config()
        self.rng = np.random.default_rng()

        self.screen = "start"
        self.level = 1
        self.hearts = INITIAL_HEARTS
        self.coins_found = 0
        self.enemies_killed = 0
        self.total_stars = 0
        self.level_stars = 0
        self.sword_equipped = False
        self.shield_equipped = False

        self.cave: Grid | None = None
        self.player: Player | None = None
        self.exit_tile: tuple[int, int] | None = None
        self.items: list[Item] = []
        self.enemies: list[Enemy] = []
        self.flash_end = 0.0
        self.attack_end = 0.0
        self.attack_tile: tuple[int, int] | None = None
        self.level_complete_end = 0.0

        self.last_tick = 0.0
        self.enemy_accumulator = 0.0

    # Reads the YAML config and overrides cave dimensions to the requested gameplay size.
    def load_config(self) -> dict:
        with open("config.yaml", encoding="utf-8") as handle:
            cfg = yaml.safe_load(handle)
        cfg["width"] = MAP_WIDTH
        cfg["height"] = MAP_HEIGHT
        return cfg

    # Runs the existing cellular automata cave pipeline until it finds a roomy connected cave.
    def run_ca_pipeline(self) -> Grid:
        height = self.cfg.get("height", MAP_HEIGHT)
        width = self.cfg.get("width", MAP_WIDTH)
        fill_prob = self.cfg.get("fill_prob", 0.45)
        ca_iterations = self.cfg.get("ca_iterations", 4)
        smooth_iterations = self.cfg.get("smooth_iterations", 2)

        while True:
            grid = Grid.random(height, width, fill_prob, self.rng)
            grid = apply_rule(grid, CAVE_BORN, CAVE_SURVIVE, ca_iterations)
            grid = apply_rule(grid, SMOOTH_BORN, SMOOTH_SURVIVE, smooth_iterations)
            final, _ = flood_fill_largest(grid)
            if int(final.data.sum()) > 600:
                return final

    # Picks a faraway reachable floor tile so the exit stays deep in the cave.
    def choose_exit_tile(self, cave: Grid, start: tuple[int, int]) -> tuple[int, int]:
        dist = distance_from_start(cave, start)
        if not np.isfinite(dist).any():
            return start
        max_dist = np.nanmax(np.where(np.isfinite(dist), dist, np.nan))
        farthest = np.argwhere(dist == max_dist)
        pick = farthest[int(self.rng.integers(0, len(farthest)))]
        return int(pick[0]), int(pick[1])

    # Builds each level with the repo's cave generator and ACO-based entity placement helpers.
    def build_level_from_existing_modules(self) -> None:
        while True:
            self.cave = self.run_ca_pipeline()
            player_pos = spawn_player(self.cave, self.rng)
            sword, shield, coins, food = spawn_items(
                self.cave,
                player_pos,
                self.rng,
                coin_count=COIN_COUNT,
                food_count=FOOD_COUNT,
            )
            blocked = {player_pos, sword, shield, *coins, *food}
            enemy_positions = spawn_enemies(
                self.cave,
                player_pos,
                blocked=blocked,
                coin_positions=coins,
                rng=self.rng,
                enemy_count=ENEMY_COUNT,
            )
            if len(coins) == COIN_COUNT and len(food) == FOOD_COUNT and len(enemy_positions) == ENEMY_COUNT:
                break

        exit_tile = self.choose_exit_tile(self.cave, player_pos)
        if exit_tile in blocked or exit_tile in set(enemy_positions):
            dist = distance_from_start(self.cave, player_pos)
            floor_cells = np.argwhere(self.cave.data == 1)
            ordered = sorted(
                [(int(r), int(c)) for r, c in floor_cells],
                key=lambda cell: dist[cell[0], cell[1]],
                reverse=True,
            )
            occupied = blocked | set(enemy_positions)
            for cell in ordered:
                if cell not in occupied:
                    exit_tile = cell
                    break

        self.player = Player(*player_pos)
        self.exit_tile = exit_tile
        self.items = [Item(ITEM_SWORD, *sword), Item(ITEM_SHIELD, *shield)]
        self.items.extend(Item(ITEM_COIN, *coin) for coin in coins)
        self.items.extend(Item(ITEM_FOOD, *meal) for meal in food)
        self.enemies = [self.make_enemy(row, col) for row, col in enemy_positions]

    # Single floor tile with small stone texture variation.
    def draw_floor(self, x: int, y: int, row: int, col: int, tag: str = "") -> None:
        base = FLOOR_A if (row + col) % 2 == 0 else FLOOR_B
        self.canvas.create_rectangle(x, y, x + TILE_SIZE, y + TILE_SIZE, fill=base, width=0, tags=tag)
        self.canvas.create_line(x + 4, y + 8, x + 12, y + 8, fill="#5a636d", width=2, tags=tag)
        self.canvas.create_line(x + 18, y + 15, x + 24, y + 13, fill="#5a636d", width=2, tags=tag)
        self.canvas.create_line(x + 10, y + 25, x + 12, y + 21, fill="#5a636d", width=2, tags=tag)

    # Single wall tile with darker stone blocks and shadowing.
    def draw_wall(self, x: int, y: int, row: int, col: int, tag: str = "") -> None:
        self.canvas.create_rectangle(x, y, x + TILE_SIZE, y + TILE_SIZE, fill=WALL_A, width=0, tags=tag)
        self.canvas.create_rectangle(x, y + 22, x + TILE_SIZE, y + TILE_SIZE, fill=WALL_C, width=0, tags=tag)
        self.canvas.create_rectangle(x + 2, y + 4, x + 12, y + 12, fill=WALL_B, width=0, tags=tag)
        self.canvas.create_rectangle(x + 14, y + 3, x + 28, y + 11, fill=WALL_B, width=0, tags=tag)
        if (row + col) % 2 == 0:
            self.canvas.create_rectangle(x + 5, y + 16, x + 13, y + 20, fill="#313945", width=0, tags=tag)
        else:
            self.canvas.create_rectangle(x + 18, y + 16, x + 27, y + 20, fill="#313945", width=0, tags=tag)

    def draw_player(self, x: int, y: int, facing: str, tag: str = "") -> None:
        self.canvas.create_rectangle(x + 8, y + 10, x + 24, y + 24, fill="#5f8fda", outline="", tags=tag)
        self.canvas.create_rectangle(x + 9, y + 4, x + 23, y + 10, fill="#d8e6ff", outline="", tags=tag)
        self.canvas.create_rectangle(x + 10, y + 11, x + 13, y + 14, fill="#11151a", outline="", tags=tag)
        self.canvas.create_rectangle(x + 19, y + 11, x + 22, y + 14, fill="#11151a", outline="", tags=tag)
        self.canvas.create_rectangle(x + 13, y + 17, x + 19, y + 19, fill="#d4ae7c", outline="", tags=tag)
        self.canvas.create_rectangle(x + 10, y + 24, x + 14, y + 30, fill="#294a7f", outline="", tags=tag)
        self.canvas.create_rectangle(x + 18, y + 24, x + 22, y + 30, fill="#294a7f", outline="", tags=tag)
        if facing == "up":
            self.canvas.create_polygon(
                x + 16, y + 1, x + 11, y + 6, x + 21, y + 6, fill="#d8e6ff", outline="", tags=tag
            )
        elif facing == "down":
            self.canvas.create_polygon(
                x + 16, y + 31, x + 11, y + 26, x + 21, y + 26, fill="#d8e6ff", outline="", tags=tag
            )
        elif facing == "left":
            self.canvas.create_polygon(
                x + 1, y + 16, x + 6, y + 11, x + 6, y + 21, fill="#d8e6ff", outline="", tags=tag
            )
        else:
            self.canvas.create_polygon(
                x + 31, y + 16, x + 26, y + 11, x + 26, y + 21, fill="#d8e6ff", outline="", tags=tag
            )

    # Enemy sprite used for every goblin patrol.
    def draw_enemy(self, x: int, y: int, tag: str = "") -> None:
        self.canvas.create_rectangle(x + 6, y + 11, x + 26, y + 22, fill="#b84242", outline="", tags=tag)
        self.canvas.create_rectangle(x + 8, y + 5, x + 24, y + 11, fill="#b84242", outline="", tags=tag)
        self.canvas.create_polygon(x + 7, y + 7, x + 10, y + 2, x + 12, y + 7, fill="#efb06a", outline="", tags=tag)
        self.canvas.create_polygon(x + 25, y + 7, x + 22, y + 2, x + 20, y + 7, fill="#efb06a", outline="", tags=tag)
        self.canvas.create_rectangle(x + 10, y + 10, x + 13, y + 13, fill="#130505", outline="", tags=tag)
        self.canvas.create_rectangle(x + 19, y + 10, x + 22, y + 13, fill="#130505", outline="", tags=tag)
        self.canvas.create_rectangle(x + 10, y + 22, x + 14, y + 29, fill="#7e2323", outline="", tags=tag)
        self.canvas.create_rectangle(x + 18, y + 22, x + 22, y + 29, fill="#7e2323", outline="", tags=tag)

    # Sword sprite for world pickups and the equipped HUD icon.
    def draw_sword(self, x: int, y: int, tag: str = "") -> None:
        blade = "#c7cfd8"
        edge = "#ebf2fa"
        hilt = "#9b6a2d"
        self.canvas.create_rectangle(x + 15, y + 4, x + 17, y + 21, fill=blade, outline="", tags=tag)
        self.canvas.create_rectangle(x + 14, y + 3, x + 18, y + 7, fill=edge, outline="", tags=tag)
        self.canvas.create_rectangle(x + 12, y + 18, x + 20, y + 21, fill=hilt, outline="", tags=tag)
        self.canvas.create_rectangle(x + 14, y + 21, x + 18, y + 28, fill="#6f4922", outline="", tags=tag)

    # Shield sprite for world pickups and the equipped HUD icon.
    def draw_shield(self, x: int, y: int, tag: str = "") -> None:
        outer = "#35537c"
        inner = "#79a7d5"
        shine = "#d8e7fb"
        self.canvas.create_polygon(
            x + 16, y + 4, x + 25, y + 10, x + 22, y + 25, x + 16, y + 29, x + 10, y + 25, x + 7, y + 10,
            fill=outer,
            outline="",
            tags=tag
        )
        self.canvas.create_polygon(
            x + 16, y + 7, x + 22, y + 11, x + 20, y + 23, x + 16, y + 26, x + 12, y + 23, x + 10, y + 11,
            fill=inner,
            outline="",
            tags=tag
        )
        self.canvas.create_line(x + 16, y + 10, x + 16, y + 23, fill=shine, width=2, tags=tag)
        self.canvas.create_line(x + 12, y + 16, x + 20, y + 16, fill=shine, width=2, tags=tag)

    # Food pickup sprite as a small apple.
    def draw_food(self, x: int, y: int, tag: str = "") -> None:
        self.canvas.create_oval(x + 8, y + 8, x + 23, y + 22, fill="#c74545", outline="", tags=tag)
        self.canvas.create_rectangle(x + 14, y + 5, x + 17, y + 9, fill="#6d3f1d", outline="", tags=tag)
        self.canvas.create_oval(x + 16, y + 4, x + 24, y + 10, fill="#5da85b", outline="", tags=tag)
        self.canvas.create_oval(x + 10, y + 12, x + 13, y + 15, fill="#fbb9b9", outline="", tags=tag)

    # Coin pickup sprite with a bright center highlight.
    def draw_coin(self, x: int, y: int, tag: str = "") -> None:
        self.canvas.create_oval(x + 10, y + 7, x + 22, y + 24, fill="#9a6d1d", outline="", tags=tag)
        self.canvas.create_oval(x + 12, y + 8, x + 20, y + 23, fill=GOLD, outline="", tags=tag)
        self.canvas.create_line(x + 16, y + 11, x + 16, y + 20, fill="#fff1ab", width=2, tags=tag)

    # Animated exit portal with a pulsing glow.
    def draw_exit(self, x: int, y: int, now_ms: float, tag: str = "") -> None:
        pulse = 2 + 1.5 * math.sin(now_ms / 180.0)
        self.canvas.create_oval(
            x + 4 - pulse, y + 4 - pulse, x + 28 + pulse, y + 28 + pulse,
            fill="#193223",
            outline="#2ef07a",
            width=2,
            tags=tag
        )
        self.canvas.create_oval(x + 8, y + 8, x + 24, y + 24, fill="#67da86", outline="", tags=tag)
        self.canvas.create_oval(x + 12, y + 12, x + 20, y + 20, fill="#d2ffe0", outline="", tags=tag)

    # Heart icon for the HUD health display.
    def draw_heart_icon(self, x: int, y: int) -> None:
        self.canvas.create_oval(x, y, x + 10, y + 10, fill=HEART, outline="")
        self.canvas.create_oval(x + 8, y, x + 18, y + 10, fill=HEART, outline="")
        self.canvas.create_polygon(x - 1, y + 7, x + 9, y + 20, x + 19, y + 7, fill=HEART, outline="")

    # Star icon for the total score display.
    def draw_star_icon(self, x: int, y: int) -> None:
        self.canvas.create_polygon(
            x + 10, y,
            x + 13, y + 7,
            x + 20, y + 8,
            x + 15, y + 13,
            x + 17, y + 21,
            x + 10, y + 17,
            x + 3, y + 21,
            x + 5, y + 13,
            x, y + 8,
            x + 7, y + 7,
            fill="#efd36e",
            outline=""
        )

    # Resets persistent run state and starts a fresh game from level one.
    def start_new_run(self) -> None:
        self.level = 1
        self.hearts = INITIAL_HEARTS
        self.coins_found = 0
        self.enemies_killed = 0
        self.total_stars = 0
        self.level_stars = 0
        self.sword_equipped = False
        self.shield_equipped = False
        self.flash_end = 0.0
        self.attack_end = 0.0
        self.attack_tile = None
        self.start_level()
        self.screen = "playing"

    # Resets per-level counters and equipment then generates the next cave.
    def start_level(self) -> None:
        self.coins_found = 0
        self.enemies_killed = 0
        self.sword_equipped = False
        self.shield_equipped = False
        self.enemy_accumulator = 0.0
        self.attack_tile = None
        self.attack_end = 0.0
        self.build_level_from_existing_modules()

    # Converts an enemy spawn tile into a patrolling enemy with a random axis and radius.
    def make_enemy(self, row: int, col: int) -> Enemy:
        return Enemy(
            row=row,
            col=col,
            origin_row=row,
            origin_col=col,
            axis="horizontal" if self.rng.random() < 0.5 else "vertical",
            radius=int(self.rng.integers(2, 4)),
            direction=-1 if self.rng.random() < 0.5 else 1,
            render_row=float(row),
            render_col=float(col),
            from_row=row,
            from_col=col,
        )

    # Routes keyboard input to start, restart, movement, or attacking for the current screen.
    def on_key_press(self, event: tk.Event) -> None:
        if self.screen in {"start", "gameover"}:
            self.start_new_run()
            return

        if self.screen != "playing" or self.player is None:
            return

        key = event.keysym
        if key in MOVE_KEYS:
            self.try_move_player(MOVE_KEYS[key])
            return

        if event.keysym.lower() in ATTACK_KEYS:
            self.swing_sword()

    # Mouse start or restart from overlay screens.
    def on_click(self, _event: tk.Event) -> None:
        if self.screen in {"start", "gameover"}:
            self.start_new_run()

    # Moves the player one tile if the destination is walkable, then resolves pickups and collisions.
    def try_move_player(self, direction: str) -> None:
        assert self.player is not None
        assert self.cave is not None

        self.player.facing = direction
        dr, dc = DIRECTIONS[direction]
        next_row = self.player.row + dr
        next_col = self.player.col + dc
        if not self.is_walkable(next_row, next_col):
            return

        self.player.row = next_row
        self.player.col = next_col
        self.pick_up_items()
        self.check_enemy_collisions()
        self.check_exit_reached()

    # Attacks the tile directly in front of the player and defeats an enemy there if the sword is equipped.
    def swing_sword(self) -> None:
        if self.player is None:
            return

        dr, dc = DIRECTIONS[self.player.facing]
        target = (self.player.row + dr, self.player.col + dc)
        self.attack_tile = target
        self.attack_end = self.now_ms() + 140

        if not self.sword_equipped:
            return

        for enemy in self.enemies:
            if enemy.alive and (enemy.row, enemy.col) == target:
                enemy.alive = False
                self.enemies_killed += 1
                break

    # Applies item pickups automatically when the player steps onto their tile.
    def pick_up_items(self) -> None:
        assert self.player is not None

        remaining: list[Item] = []
        for item in self.items:
            if (item.row, item.col) != (self.player.row, self.player.col):
                remaining.append(item)
                continue

            if item.kind == ITEM_SWORD:
                self.sword_equipped = True
            elif item.kind == ITEM_SHIELD:
                self.shield_equipped = True
            elif item.kind == ITEM_FOOD:
                self.hearts = min(MAX_HEARTS, self.hearts + 1)
            elif item.kind == ITEM_COIN:
                self.coins_found += 1

        self.items = remaining

    # Checks whether any living enemy is occupying the same tile as the player.
    def check_enemy_collisions(self) -> None:
        assert self.player is not None
        if any(enemy.alive and (enemy.row, enemy.col) == (self.player.row, self.player.col) for enemy in self.enemies):
            self.damage_player()

    # Handles shield blocking, heart loss, invulnerability flashing, and the game over transition.
    def damage_player(self) -> None:
        if self.now_ms() < self.flash_end:
            return

        if self.shield_equipped:
            self.shield_equipped = False
        else:
            self.hearts -= 1

        self.flash_end = self.now_ms() + 450
        if self.hearts <= 0:
            self.screen = "gameover"

    # Advances enemy patrols on a timer and interpolates render positions for smoother motion.
    def move_enemies(self, delta_ms: float) -> None:
        assert self.cave is not None
        assert self.player is not None

        self.enemy_accumulator += delta_ms
        while self.enemy_accumulator >= ENEMY_MOVE_MS:
            self.enemy_accumulator -= ENEMY_MOVE_MS
            living_positions = {
                (enemy.row, enemy.col)
                for enemy in self.enemies
                if enemy.alive
            }
            for enemy in self.enemies:
                if not enemy.alive:
                    continue

                living_positions.discard((enemy.row, enemy.col))
                dr, dc = (0, enemy.direction) if enemy.axis == "horizontal" else (enemy.direction, 0)
                next_row = enemy.row + dr
                next_col = enemy.col + dc
                origin_delta = (
                    next_col - enemy.origin_col
                    if enemy.axis == "horizontal"
                    else next_row - enemy.origin_row
                )
                blocked = (
                    not self.is_walkable(next_row, next_col)
                    or abs(origin_delta) > enemy.radius
                    or (next_row, next_col) in living_positions
                )
                if blocked:
                    enemy.direction *= -1
                    dr, dc = (0, enemy.direction) if enemy.axis == "horizontal" else (enemy.direction, 0)
                    next_row = enemy.row + dr
                    next_col = enemy.col + dc
                    origin_delta = (
                        next_col - enemy.origin_col
                        if enemy.axis == "horizontal"
                        else next_row - enemy.origin_row
                    )
                    if (
                        not self.is_walkable(next_row, next_col)
                        or abs(origin_delta) > enemy.radius
                        or (next_row, next_col) in living_positions
                    ):
                        enemy.from_row = enemy.row
                        enemy.from_col = enemy.col
                        enemy.render_row = float(enemy.row)
                        enemy.render_col = float(enemy.col)
                        living_positions.add((enemy.row, enemy.col))
                        continue

                enemy.from_row = enemy.row
                enemy.from_col = enemy.col
                enemy.row = next_row
                enemy.col = next_col
                living_positions.add((enemy.row, enemy.col))
                if (enemy.row, enemy.col) == (self.player.row, self.player.col):
                    self.damage_player()

        progress = min(1.0, self.enemy_accumulator / ENEMY_MOVE_MS)
        for enemy in self.enemies:
            if not enemy.alive:
                continue
            enemy.render_row = enemy.from_row + (enemy.row - enemy.from_row) * progress
            enemy.render_col = enemy.from_col + (enemy.col - enemy.from_col) * progress

    # Awards end-of-level stars when the player reaches the exit tile.
    def check_exit_reached(self) -> None:
        assert self.player is not None
        if (self.player.row, self.player.col) != self.exit_tile:
            return

        stars = 1
        if self.coins_found == COIN_COUNT:
            stars += 1
        if self.enemies_killed == ENEMY_COUNT:
            stars += 1
        self.total_stars += stars
        self.level_stars = stars
        self.screen = "levelcomplete"
        self.level_complete_end = self.now_ms() + LEVEL_COMPLETE_MS

    # Main frame loop advancing game state and scheduling the next repaint.
    def update(self) -> None:
        now = self.now_ms()
        if self.last_tick == 0.0:
            self.last_tick = now
        delta = min(50.0, now - self.last_tick)
        self.last_tick = now

        if self.screen == "playing":
            self.move_enemies(delta)
        elif self.screen == "levelcomplete" and now >= self.level_complete_end:
            self.level += 1
            self.start_level()
            self.screen = "playing"

        self.render()
        self.root.after(FRAME_MS, self.update)

    # Top-left tile of the clamped 10x10 camera window around the player.
    def get_camera_origin(self) -> tuple[int, int]:
        assert self.player is not None

        max_row = MAP_HEIGHT - VIEW_TILES
        max_col = MAP_WIDTH - VIEW_TILES
        row = self.player.row - VIEW_TILES // 2
        col = self.player.col - VIEW_TILES // 2
        row = max(0, min(max_row, row))
        col = max(0, min(max_col, col))
        return row, col

    # Clears the canvas and draws the appropriate world or overlay screen for the current state.
    def render(self) -> None:
        self.canvas.delete("all")
        self.draw_background()
        self.draw_hud()

        if self.screen == "start":
            self.draw_start_screen()
            return

        self.draw_world()

        if self.screen == "levelcomplete":
            self.draw_overlay(
                "Level Complete!",
                f"Stars earned this level: {self.level_stars}",
                f"Descending to cave {self.level + 1}..."
            )
        elif self.screen == "gameover":
            self.draw_overlay(
                "Game Over",
                f"Stars collected: {self.total_stars}",
                "Press any key or click to restart"
            )

    # Backdrop, HUD panel, and border around the scaled world viewport.
    def draw_background(self) -> None:
        self.canvas.create_rectangle(0, 0, self.window_width, self.window_height, fill=BG, width=0)
        self.canvas.create_rectangle(10, 10, self.window_width - 10, HUD_HEIGHT - 10, fill=PANEL, outline=PANEL_EDGE, width=2)
        self.canvas.create_rectangle(
            0,
            HUD_HEIGHT,
            self.window_width,
            self.window_height,
            fill=SHADOW,
            width=0,
        )
        self.canvas.create_rectangle(
            self.world_left - 4,
            HUD_HEIGHT - 4,
            self.world_left + self.viewport_width + 4,
            HUD_HEIGHT + self.viewport_height + 4,
            outline=PANEL_EDGE,
            width=2,
        )

    # Visible cave slice, entities, attack marker, and player in the scaled world layer.
    def draw_world(self) -> None:
        assert self.cave is not None
        assert self.player is not None
        assert self.exit_tile is not None

        cam_row, cam_col = self.get_camera_origin()
        top = HUD_HEIGHT
        now = self.now_ms()

        for view_r in range(VIEW_TILES):
            for view_c in range(VIEW_TILES):
                row = cam_row + view_r
                col = cam_col + view_c
                x = self.world_left + view_c * TILE_SIZE
                y = top + view_r * TILE_SIZE
                if self.cave.data[row, col] == 1:
                    self.draw_floor(x, y, row, col, "world")
                else:
                    self.draw_wall(x, y, row, col, "world")

        exit_row, exit_col = self.exit_tile
        if cam_row <= exit_row < cam_row + VIEW_TILES and cam_col <= exit_col < cam_col + VIEW_TILES:
            self.draw_exit(self.world_left + (exit_col - cam_col) * TILE_SIZE, top + (exit_row - cam_row) * TILE_SIZE, now, "world")

        for item in self.items:
            if not (cam_row <= item.row < cam_row + VIEW_TILES and cam_col <= item.col < cam_col + VIEW_TILES):
                continue
            x = self.world_left + (item.col - cam_col) * TILE_SIZE
            y = top + (item.row - cam_row) * TILE_SIZE
            if item.kind == ITEM_SWORD:
                self.draw_sword(x, y, "world")
            elif item.kind == ITEM_SHIELD:
                self.draw_shield(x, y, "world")
            elif item.kind == ITEM_FOOD:
                self.draw_food(x, y, "world")
            elif item.kind == ITEM_COIN:
                self.draw_coin(x, y, "world")

        for enemy in self.enemies:
            if not enemy.alive:
                continue
            if not (
                cam_row <= enemy.render_row < cam_row + VIEW_TILES
                and cam_col <= enemy.render_col < cam_col + VIEW_TILES
            ):
                continue
            x = self.world_left + int(round((enemy.render_col - cam_col) * TILE_SIZE))
            y = top + int(round((enemy.render_row - cam_row) * TILE_SIZE))
            self.draw_enemy(x, y, "world")

        if self.attack_tile and now < self.attack_end:
            attack_row, attack_col = self.attack_tile
            if cam_row <= attack_row < cam_row + VIEW_TILES and cam_col <= attack_col < cam_col + VIEW_TILES:
                x = self.world_left + (attack_col - cam_col) * TILE_SIZE
                y = top + (attack_row - cam_row) * TILE_SIZE
                color = "#f9e9a4" if self.sword_equipped else "#909090"
                self.canvas.create_rectangle(x + 5, y + 5, x + TILE_SIZE - 5, y + TILE_SIZE - 5, outline=color, width=2, tags="world")
        elif now >= self.attack_end:
            self.attack_tile = None

        px = self.world_left + (self.player.col - cam_col) * TILE_SIZE
        py = top + (self.player.row - cam_row) * TILE_SIZE
        if now < self.flash_end and int(now / 80) % 2 == 0:
            self.canvas.create_rectangle(px, py, px + TILE_SIZE, py + TILE_SIZE, fill="#f4f4f4", width=0, tags="world")
        self.draw_player(px, py, self.player.facing, "world")

        self.canvas.scale("world", self.world_left, HUD_HEIGHT, self.render_scale, self.render_scale)

        self.canvas.create_text(
            self.world_left,
            HUD_HEIGHT + 16,
            anchor="w",
            fill="#dce5ef",
            font=("Trebuchet MS", 12, "bold"),
            text=f"Level {self.level}",
        )

    # Top HUD with hearts, counters, and equipment indicators.
    def draw_hud(self) -> None:
        self.canvas.create_text(20, 28, anchor="w", fill=TEXT_MUTED, font=("Trebuchet MS", 10, "bold"), text="HEARTS")
        heart_x = 18
        for _ in range(self.hearts):
            self.draw_heart_icon(heart_x, 42)
            heart_x += 26

        self.canvas.create_text(160, 28, anchor="w", fill=TEXT_MUTED, font=("Trebuchet MS", 10, "bold"), text="COINS")
        self.canvas.create_text(160, 52, anchor="w", fill=TEXT, font=("Trebuchet MS", 16, "bold"), text=f"{self.coins_found} / {COIN_COUNT}")

        self.canvas.create_text(250, 28, anchor="w", fill=TEXT_MUTED, font=("Trebuchet MS", 10, "bold"), text="ENEMIES")
        self.canvas.create_text(250, 52, anchor="w", fill=TEXT, font=("Trebuchet MS", 16, "bold"), text=f"{self.enemies_killed} / {ENEMY_COUNT}")

        self.canvas.create_text(20, 108, anchor="w", fill=TEXT_MUTED, font=("Trebuchet MS", 10, "bold"), text="SWORD")
        if self.sword_equipped:
            self.draw_sword(78, 92)

        self.canvas.create_text(140, 108, anchor="w", fill=TEXT_MUTED, font=("Trebuchet MS", 10, "bold"), text="SHIELD")
        if self.shield_equipped:
            self.draw_shield(208, 90)

        self.canvas.create_text(265, 108, anchor="w", fill=TEXT_MUTED, font=("Trebuchet MS", 10, "bold"), text="STARS")
        self.draw_star_icon(314, 91)
        self.canvas.create_text(344, 103, anchor="w", fill=TEXT, font=("Trebuchet MS", 16, "bold"), text=str(self.total_stars))

    # Start screen instructions inside the game frame.
    def draw_start_screen(self) -> None:
        self.canvas.create_rectangle(14, HUD_HEIGHT + 20, self.window_width - 14, self.window_height - 18, fill=PANEL, outline=PANEL_EDGE, width=2)
        self.canvas.create_text(
            self.window_width / 2,
            HUD_HEIGHT + 56,
            fill=TEXT,
            font=("Trebuchet MS", 24, "bold"),
            text="Dungeon Crawler",
        )
        self.canvas.create_text(
            self.window_width / 2,
            HUD_HEIGHT + 114,
            fill="#bcc7d2",
            font=("Trebuchet MS", 13),
            width=self.window_width - 60,
            justify="center",
            text=(
                "\n\n\nArrow keys move through the cave. "
                "Pick up the sword each level, then press Space to attack the tile in front of you.\n"
                "The shield blocks one hit, food restores one heart up to five, and both sword and shield reset on the next level.\n"
                "Reach the exit for a star, but collect all coins and defeat all enemies for bonus stars."
            ),
        )
        pulse = 0.65 + 0.35 * math.sin(self.now_ms() / 260.0)
        color = "#9de587" if pulse > 0.75 else "#77be68"
        self.canvas.create_text(
            self.window_width / 2,
            HUD_HEIGHT + 208,
            fill=color,
            font=("Trebuchet MS", 18, "bold"),
            text="\n\nPress any key or click to start",
        )

    # Centered overlay panels for level completion and game over states.
    def draw_overlay(self, title: str, subtitle: str, footer: str) -> None:
        self.canvas.create_rectangle(20, HUD_HEIGHT + 50, self.window_width - 20, self.window_height - 50, fill="#12171d", outline=PANEL_EDGE, width=3)
        self.canvas.create_text(self.window_width / 2, HUD_HEIGHT + 110, fill=TEXT, font=("Trebuchet MS", 24, "bold"), text=title)
        self.canvas.create_text(self.window_width / 2, HUD_HEIGHT + 150, fill="#d3dbe5", font=("Trebuchet MS", 16, "bold"), text=subtitle)
        self.canvas.create_text(self.window_width / 2, HUD_HEIGHT + 195, fill=TEXT_MUTED, font=("Trebuchet MS", 13), text=footer)

    # Grid cell inside bounds and marked as floor in the cave data.
    def is_walkable(self, row: int, col: int) -> bool:
        assert self.cave is not None
        return 0 <= row < MAP_HEIGHT and 0 <= col < MAP_WIDTH and self.cave.data[row, col] == 1

    # Current Tk clock time in milliseconds for animation timing.
    def now_ms(self) -> float:
        return float(self.root.tk.call("clock", "milliseconds"))

    # Starts the frame loop and enters the Tkinter event loop.
    def run(self) -> None:
        self.update()
        self.root.mainloop()


# Launches the desktop dungeon crawler when the script is run directly.
if __name__ == "__main__":
    DungeonCrawlerGame().run()
