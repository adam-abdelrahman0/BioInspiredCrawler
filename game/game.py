import math
import tkinter as tk

import numpy as np
import yaml

from ca import Grid, run_ca_pipeline
from entities import spawn_enemies, spawn_items, spawn_player
from entities.aco import distance_from_start
from entities.boids import boids_step, spawn_boid_swarm

from .constants import (
    ATTACK_KEYS,
    BG,
    BOID_COUNT,
    BOID_MOVE_MS,
    COIN_COUNT,
    DIRECTIONS,
    ENEMY_COUNT,
    ENEMY_MOVE_MS,
    FOOD_COUNT,
    FRAME_MS,
    HUD_HEIGHT,
    INITIAL_HEARTS,
    ITEM_COIN,
    ITEM_FOOD,
    ITEM_SHIELD,
    ITEM_SWORD,
    LEVEL_COMPLETE_MS,
    LIGHT_RADIUS,
    PLAYER_MOVE_MS,
    MAP_HEIGHT,
    MAP_WIDTH,
    MAX_HEARTS,
    MOVE_KEYS,
    PANEL,
    PANEL_EDGE,
    SHADOW,
    TEXT,
    TEXT_MUTED,
    TILE_SIZE,
    VIEW_TILES,
    VIEWPORT_HEIGHT,
    VIEWPORT_WIDTH,
    WINDOW_PADDING,
)
from .sprites import (
    draw_boid_enemy,
    draw_coin,
    draw_enemy,
    draw_exit,
    draw_floor,
    draw_food,
    draw_heart_icon,
    draw_player,
    draw_shield,
    draw_star_icon,
    draw_sword,
    draw_wall,
)
from .types import BoidEnemy, Enemy, Item, Player

_FOG_START = LIGHT_RADIUS - 3.0  # distance at which darkening begins


class DungeonCrawlerGame:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Dungeon Crawler")
        self.root.resizable(False, False)
        self.root.configure(bg=BG)
        self.root.update_idletasks()

        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        horizontal_scale = max(
            1.0, (screen_width - (WINDOW_PADDING * 2)) / VIEWPORT_WIDTH
        )
        vertical_scale = max(1.0, (screen_height - HUD_HEIGHT - 160) / VIEWPORT_HEIGHT)
        self.render_scale = min(horizontal_scale, vertical_scale)
        self.window_width = int(VIEWPORT_WIDTH * self.render_scale) + (
            WINDOW_PADDING * 2
        )
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
        self.root.bind("<KeyRelease>", self.on_key_release)
        self.canvas.bind("<Button-1>", self.on_click)

        self.cfg = self._load_config()
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
        self.boid_enemies: list[BoidEnemy] = []
        self.flash_end = 0.0
        self.attack_end = 0.0
        self.attack_tile: tuple[int, int] | None = None
        self.level_complete_end = 0.0

        self.last_tick = 0.0
        self.enemy_accumulator = 0.0
        self.boid_accumulator = 0.0
        self.held_direction: str | None = None

    # ------------------------------------------------------------------ config

    def _load_config(self) -> dict:
        with open("config.yaml", encoding="utf-8") as handle:
            cfg = yaml.safe_load(handle)
        cfg["width"] = MAP_WIDTH
        cfg["height"] = MAP_HEIGHT
        return cfg

    # ---------------------------------------------------------------- level gen

    def generate_cave(self) -> Grid:
        height = self.cfg.get("height", MAP_HEIGHT)
        width = self.cfg.get("width", MAP_WIDTH)
        fill_prob = self.cfg.get("fill_prob", 0.45)
        ca_iterations = self.cfg.get("ca_iterations", 4)
        smooth_iterations = self.cfg.get("smooth_iterations", 2)

        while True:
            _raw, final, _regions = run_ca_pipeline(
                height, width, fill_prob, ca_iterations, smooth_iterations, self.rng
            )
            if int(final.data.sum()) > 600:
                return final

    def _choose_exit_tile(self, cave: Grid, start: tuple[int, int]) -> tuple[int, int]:
        dist = distance_from_start(cave, start)
        if not np.isfinite(dist).any():
            return start
        max_dist = np.nanmax(np.where(np.isfinite(dist), dist, np.nan))
        farthest = np.argwhere(dist == max_dist)
        pick = farthest[int(self.rng.integers(0, len(farthest)))]
        return int(pick[0]), int(pick[1])

    def _build_level(self) -> None:
        while True:
            self.cave = self.generate_cave()
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
            if (
                len(coins) == COIN_COUNT
                and len(food) == FOOD_COUNT
                and len(enemy_positions) == ENEMY_COUNT
            ):
                break

        all_blocked = blocked | set(enemy_positions)

        exit_tile = self._choose_exit_tile(self.cave, player_pos)
        if exit_tile in all_blocked:
            dist = distance_from_start(self.cave, player_pos)
            floor_cells = np.argwhere(self.cave.data == 1)
            ordered = sorted(
                [(int(r), int(c)) for r, c in floor_cells],
                key=lambda cell: dist[cell[0], cell[1]],
                reverse=True,
            )
            for cell in ordered:
                if cell not in all_blocked:
                    exit_tile = cell
                    break

        boid_positions = spawn_boid_swarm(
            self.cave,
            center=exit_tile,
            blocked=all_blocked | {exit_tile},
            rng=self.rng,
            count=BOID_COUNT,
        )

        self.player = Player(*player_pos)
        self.exit_tile = exit_tile
        self.items = [Item(ITEM_SWORD, *sword), Item(ITEM_SHIELD, *shield)]
        self.items.extend(Item(ITEM_COIN, *coin) for coin in coins)
        self.items.extend(Item(ITEM_FOOD, *meal) for meal in food)
        self.enemies = [self._make_enemy(row, col) for row, col in enemy_positions]
        self.boid_enemies = [
            BoidEnemy(
                row=r,
                col=c,
                render_row=float(r),
                render_col=float(c),
                from_row=r,
                from_col=c,
            )
            for r, c in boid_positions
        ]

    def _make_enemy(self, row: int, col: int) -> Enemy:
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

    # ---------------------------------------------------------- game lifecycle

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
        self._start_level()
        self.screen = "playing"

    def _start_level(self) -> None:
        self.coins_found = 0
        self.enemies_killed = 0
        self.sword_equipped = False
        self.shield_equipped = False
        self.enemy_accumulator = 0.0
        self.boid_accumulator = 0.0
        self.attack_tile = None
        self.attack_end = 0.0
        self._build_level()

    # ------------------------------------------------------------ input / actions

    def on_key_press(self, event: tk.Event) -> None:
        if self.screen in {"start", "gameover"}:
            self.start_new_run()
            return
        if self.screen != "playing" or self.player is None:
            return
        key = event.keysym
        if key in MOVE_KEYS:
            direction = MOVE_KEYS[key]
            self.held_direction = direction
            # Only start a move if the current animation has finished — otherwise
            # the auto-chain in _update_player_render will pick it up next frame.
            elapsed = self._now_ms() - self.player.move_start_ms
            if elapsed >= PLAYER_MOVE_MS:
                self._try_move_player(direction)
        elif event.keysym.lower() in ATTACK_KEYS:
            self._swing_sword()

    def on_key_release(self, event: tk.Event) -> None:
        key = event.keysym
        if key in MOVE_KEYS and self.held_direction == MOVE_KEYS[key]:
            self.held_direction = None

    def on_click(self, _event: tk.Event) -> None:
        if self.screen in {"start", "gameover"}:
            self.start_new_run()

    def _try_move_player(self, direction: str) -> None:
        assert self.player is not None
        assert self.cave is not None
        self.player.facing = direction
        dr, dc = DIRECTIONS[direction]
        next_row = self.player.row + dr
        next_col = self.player.col + dc
        if not self._is_walkable(next_row, next_col):
            return
        self.player.from_row = self.player.render_row
        self.player.from_col = self.player.render_col
        self.player.row = next_row
        self.player.col = next_col
        self.player.move_start_ms = self._now_ms()
        self._pick_up_items()
        self._check_enemy_collisions()
        self._check_exit_reached()

    def _swing_sword(self) -> None:
        if self.player is None:
            return
        dr, dc = DIRECTIONS[self.player.facing]
        target = (self.player.row + dr, self.player.col + dc)
        self.attack_tile = target
        self.attack_end = self._now_ms() + 140
        if not self.sword_equipped:
            return
        for enemy in self.enemies:
            if enemy.alive and (enemy.row, enemy.col) == target:
                enemy.alive = False
                self.enemies_killed += 1
                return
        for enemy in self.boid_enemies:
            if enemy.alive and (enemy.row, enemy.col) == target:
                enemy.alive = False
                self.enemies_killed += 1
                return

    def _pick_up_items(self) -> None:
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

    def _check_enemy_collisions(self) -> None:
        assert self.player is not None
        pr, pc = self.player.row, self.player.col
        if any(e.alive and (e.row, e.col) == (pr, pc) for e in self.enemies) or any(
            e.alive and (e.row, e.col) == (pr, pc) for e in self.boid_enemies
        ):
            self._damage_player()

    def _damage_player(self) -> None:
        if self._now_ms() < self.flash_end:
            return
        if self.shield_equipped:
            self.shield_equipped = False
        else:
            self.hearts -= 1
        self.flash_end = self._now_ms() + 450
        if self.hearts <= 0:
            self.screen = "gameover"

    def _check_exit_reached(self) -> None:
        assert self.player is not None
        if (self.player.row, self.player.col) != self.exit_tile:
            return
        stars = 1
        if self.coins_found == COIN_COUNT:
            stars += 1
        if self.enemies_killed == ENEMY_COUNT + len(self.boid_enemies):
            stars += 1
        self.total_stars += stars
        self.level_stars = stars
        self.screen = "levelcomplete"
        self.level_complete_end = self._now_ms() + LEVEL_COMPLETE_MS

    # ------------------------------------------------------------ enemy movement

    def _move_enemies(self, delta_ms: float) -> None:
        assert self.cave is not None
        assert self.player is not None

        self.enemy_accumulator += delta_ms
        while self.enemy_accumulator >= ENEMY_MOVE_MS:
            self.enemy_accumulator -= ENEMY_MOVE_MS
            living_positions = {(e.row, e.col) for e in self.enemies if e.alive}
            for enemy in self.enemies:
                if not enemy.alive:
                    continue
                living_positions.discard((enemy.row, enemy.col))
                dr, dc = (
                    (0, enemy.direction)
                    if enemy.axis == "horizontal"
                    else (enemy.direction, 0)
                )
                next_row = enemy.row + dr
                next_col = enemy.col + dc
                origin_delta = (
                    next_col - enemy.origin_col
                    if enemy.axis == "horizontal"
                    else next_row - enemy.origin_row
                )
                blocked = (
                    not self._is_walkable(next_row, next_col)
                    or abs(origin_delta) > enemy.radius
                    or (next_row, next_col) in living_positions
                )
                if blocked:
                    enemy.direction *= -1
                    dr, dc = (
                        (0, enemy.direction)
                        if enemy.axis == "horizontal"
                        else (enemy.direction, 0)
                    )
                    next_row = enemy.row + dr
                    next_col = enemy.col + dc
                    origin_delta = (
                        next_col - enemy.origin_col
                        if enemy.axis == "horizontal"
                        else next_row - enemy.origin_row
                    )
                    if (
                        not self._is_walkable(next_row, next_col)
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
                    self._damage_player()

        progress = min(1.0, self.enemy_accumulator / ENEMY_MOVE_MS)
        for enemy in self.enemies:
            if not enemy.alive:
                continue
            enemy.render_row = enemy.from_row + (enemy.row - enemy.from_row) * progress
            enemy.render_col = enemy.from_col + (enemy.col - enemy.from_col) * progress

    # ------------------------------------------------------------ boid movement

    def _move_boids(self, delta_ms: float) -> None:
        assert self.cave is not None
        assert self.player is not None

        self.boid_accumulator += delta_ms
        while self.boid_accumulator >= BOID_MOVE_MS:
            self.boid_accumulator -= BOID_MOVE_MS

            positions = np.array(
                [[e.row, e.col] for e in self.boid_enemies], dtype=float
            )
            velocities = np.array(
                [[e.vel_row, e.vel_col] for e in self.boid_enemies], dtype=float
            )
            alive = np.array([e.alive for e in self.boid_enemies], dtype=bool)

            new_pos, new_vel, from_pos = boids_step(
                positions,
                velocities,
                alive,
                (self.player.row, self.player.col),
                self.cave,
                self.rng,
            )

            for i, enemy in enumerate(self.boid_enemies):
                if not enemy.alive:
                    continue
                enemy.from_row = int(from_pos[i, 0])
                enemy.from_col = int(from_pos[i, 1])
                enemy.row = int(new_pos[i, 0])
                enemy.col = int(new_pos[i, 1])
                enemy.vel_row = float(new_vel[i, 0])
                enemy.vel_col = float(new_vel[i, 1])
                if (enemy.row, enemy.col) == (self.player.row, self.player.col):
                    self._damage_player()

        progress = min(1.0, self.boid_accumulator / BOID_MOVE_MS)
        for enemy in self.boid_enemies:
            if not enemy.alive:
                continue
            enemy.render_row = enemy.from_row + (enemy.row - enemy.from_row) * progress
            enemy.render_col = enemy.from_col + (enemy.col - enemy.from_col) * progress

    # ---------------------------------------------------------- player animation

    def _update_player_render(self) -> None:
        if self.player is None:
            return
        t = min(1.0, (self._now_ms() - self.player.move_start_ms) / PLAYER_MOVE_MS)
        self.player.render_row = (
            self.player.from_row + (self.player.row - self.player.from_row) * t
        )
        self.player.render_col = (
            self.player.from_col + (self.player.col - self.player.from_col) * t
        )
        if t >= 1.0 and self.held_direction is not None:
            self._try_move_player(self.held_direction)

    # --------------------------------------------------------------- game loop

    def update(self) -> None:
        now = self._now_ms()
        if self.last_tick == 0.0:
            self.last_tick = now
        delta = min(50.0, now - self.last_tick)
        self.last_tick = now

        if self.screen == "playing":
            self._move_enemies(delta)
            self._move_boids(delta)
            self._update_player_render()
        elif self.screen == "levelcomplete" and now >= self.level_complete_end:
            self.level += 1
            self._start_level()
            self.screen = "playing"

        self.render()
        self.root.after(FRAME_MS, self.update)

    # ------------------------------------------------------------- rendering

    def render(self) -> None:
        self.canvas.delete("all")
        self._draw_background()
        self._draw_hud()

        if self.screen == "start":
            self._draw_start_screen()
            return

        self._draw_world()

        if self.screen == "levelcomplete":
            self._draw_overlay(
                "Level Complete!",
                f"Stars earned this level: {self.level_stars}",
                f"Descending to cave {self.level + 1}...",
            )
        elif self.screen == "gameover":
            self._draw_overlay(
                "Game Over",
                f"Stars collected: {self.total_stars}",
                "Press any key or click to restart",
            )

    def _draw_background(self) -> None:
        self.canvas.create_rectangle(
            0, 0, self.window_width, self.window_height, fill=BG, width=0
        )
        self.canvas.create_rectangle(
            10,
            10,
            self.window_width - 10,
            HUD_HEIGHT - 10,
            fill=PANEL,
            outline=PANEL_EDGE,
            width=2,
        )
        self.canvas.create_rectangle(
            0, HUD_HEIGHT, self.window_width, self.window_height, fill=SHADOW, width=0
        )
        self.canvas.create_rectangle(
            self.world_left - 4,
            HUD_HEIGHT - 4,
            self.world_left + self.viewport_width + 4,
            HUD_HEIGHT + self.viewport_height + 4,
            outline=PANEL_EDGE,
            width=2,
        )

    def _draw_world(self) -> None:
        assert self.cave is not None
        assert self.player is not None
        assert self.exit_tile is not None

        cam_row, cam_col = self._get_camera_origin()
        top = HUD_HEIGHT
        now = self._now_ms()

        for view_r in range(VIEW_TILES):
            for view_c in range(VIEW_TILES):
                row = cam_row + view_r
                col = cam_col + view_c
                x = self.world_left + view_c * TILE_SIZE
                y = top + view_r * TILE_SIZE
                dist = math.sqrt(
                    (row - self.player.render_row) ** 2
                    + (col - self.player.render_col) ** 2
                )
                if dist >= LIGHT_RADIUS:
                    self.canvas.create_rectangle(
                        x,
                        y,
                        x + TILE_SIZE,
                        y + TILE_SIZE,
                        fill=BG,
                        width=0,
                        tags="world",
                    )
                    continue
                brightness = max(
                    0.0,
                    1.0 - max(0.0, dist - _FOG_START) / (LIGHT_RADIUS - _FOG_START),
                )
                if self.cave.data[row, col] == 1:
                    draw_floor(self.canvas, x, y, row, col, "world", brightness)
                else:
                    draw_wall(self.canvas, x, y, row, col, "world", brightness)

        exit_row, exit_col = self.exit_tile
        if (
            cam_row <= exit_row < cam_row + VIEW_TILES
            and cam_col <= exit_col < cam_col + VIEW_TILES
        ):
            draw_exit(
                self.canvas,
                self.world_left + (exit_col - cam_col) * TILE_SIZE,
                top + (exit_row - cam_row) * TILE_SIZE,
                now,
                "world",
            )

        for item in self.items:
            if not (
                cam_row <= item.row < cam_row + VIEW_TILES
                and cam_col <= item.col < cam_col + VIEW_TILES
            ):
                continue
            x = self.world_left + (item.col - cam_col) * TILE_SIZE
            y = top + (item.row - cam_row) * TILE_SIZE
            if item.kind == ITEM_SWORD:
                draw_sword(self.canvas, x, y, "world")
            elif item.kind == ITEM_SHIELD:
                draw_shield(self.canvas, x, y, "world")
            elif item.kind == ITEM_FOOD:
                draw_food(self.canvas, x, y, "world")
            elif item.kind == ITEM_COIN:
                draw_coin(self.canvas, x, y, "world")

        for enemy in self.enemies:
            if not enemy.alive:
                continue
            if not (
                cam_row <= enemy.render_row < cam_row + VIEW_TILES
                and cam_col <= enemy.render_col < cam_col + VIEW_TILES
            ):
                continue
            x = self.world_left + round((enemy.render_col - cam_col) * TILE_SIZE)
            y = top + round((enemy.render_row - cam_row) * TILE_SIZE)
            draw_enemy(self.canvas, x, y, "world")

        for enemy in self.boid_enemies:
            if not enemy.alive:
                continue
            if not (
                cam_row <= enemy.render_row < cam_row + VIEW_TILES
                and cam_col <= enemy.render_col < cam_col + VIEW_TILES
            ):
                continue
            x = self.world_left + round((enemy.render_col - cam_col) * TILE_SIZE)
            y = top + round((enemy.render_row - cam_row) * TILE_SIZE)
            draw_boid_enemy(self.canvas, x, y, "world")

        if self.attack_tile and now < self.attack_end:
            attack_row, attack_col = self.attack_tile
            if (
                cam_row <= attack_row < cam_row + VIEW_TILES
                and cam_col <= attack_col < cam_col + VIEW_TILES
            ):
                x = self.world_left + (attack_col - cam_col) * TILE_SIZE
                y = top + (attack_row - cam_row) * TILE_SIZE
                color = "#f9e9a4" if self.sword_equipped else "#909090"
                self.canvas.create_rectangle(
                    x + 5,
                    y + 5,
                    x + TILE_SIZE - 5,
                    y + TILE_SIZE - 5,
                    outline=color,
                    width=2,
                    tags="world",
                )
        elif now >= self.attack_end:
            self.attack_tile = None

        px = self.world_left + round((self.player.render_col - cam_col) * TILE_SIZE)
        py = top + round((self.player.render_row - cam_row) * TILE_SIZE)
        if now < self.flash_end and int(now / 80) % 2 == 0:
            self.canvas.create_rectangle(
                px,
                py,
                px + TILE_SIZE,
                py + TILE_SIZE,
                fill="#f4f4f4",
                width=0,
                tags="world",
            )
        draw_player(self.canvas, px, py, self.player.facing, "world")

        self.canvas.scale(
            "world", self.world_left, HUD_HEIGHT, self.render_scale, self.render_scale
        )
        self.canvas.create_text(
            self.world_left,
            HUD_HEIGHT + 16,
            anchor="w",
            fill="#dce5ef",
            font=("Trebuchet MS", 12, "bold"),
            text=f"Level {self.level}",
        )

    def _draw_hud(self) -> None:
        self.canvas.create_text(
            20,
            28,
            anchor="w",
            fill=TEXT_MUTED,
            font=("Trebuchet MS", 10, "bold"),
            text="HEARTS",
        )
        heart_x = 18
        for _ in range(self.hearts):
            draw_heart_icon(self.canvas, heart_x, 42)
            heart_x += 26

        self.canvas.create_text(
            160,
            28,
            anchor="w",
            fill=TEXT_MUTED,
            font=("Trebuchet MS", 10, "bold"),
            text="COINS",
        )
        self.canvas.create_text(
            160,
            52,
            anchor="w",
            fill=TEXT,
            font=("Trebuchet MS", 16, "bold"),
            text=f"{self.coins_found} / {COIN_COUNT}",
        )

        self.canvas.create_text(
            250,
            28,
            anchor="w",
            fill=TEXT_MUTED,
            font=("Trebuchet MS", 10, "bold"),
            text="ENEMIES",
        )
        self.canvas.create_text(
            250,
            52,
            anchor="w",
            fill=TEXT,
            font=("Trebuchet MS", 16, "bold"),
            text=f"{self.enemies_killed} / {ENEMY_COUNT + len(self.boid_enemies)}",
        )

        self.canvas.create_text(
            20,
            108,
            anchor="w",
            fill=TEXT_MUTED,
            font=("Trebuchet MS", 10, "bold"),
            text="SWORD",
        )
        if self.sword_equipped:
            draw_sword(self.canvas, 78, 92)

        self.canvas.create_text(
            140,
            108,
            anchor="w",
            fill=TEXT_MUTED,
            font=("Trebuchet MS", 10, "bold"),
            text="SHIELD",
        )
        if self.shield_equipped:
            draw_shield(self.canvas, 208, 90)

        self.canvas.create_text(
            265,
            108,
            anchor="w",
            fill=TEXT_MUTED,
            font=("Trebuchet MS", 10, "bold"),
            text="STARS",
        )
        draw_star_icon(self.canvas, 314, 91)
        self.canvas.create_text(
            344,
            103,
            anchor="w",
            fill=TEXT,
            font=("Trebuchet MS", 16, "bold"),
            text=str(self.total_stars),
        )
        if self.screen == "playing":
            self._draw_exit_compass()

    def _draw_exit_compass(self) -> None:
        if self.player is None or self.exit_tile is None:
            return
        cx = self.window_width - 52
        cy = 57
        r = 18

        dr = self.exit_tile[0] - self.player.row
        dc = self.exit_tile[1] - self.player.col
        dist_tiles = math.sqrt(dr * dr + dc * dc)

        self.canvas.create_text(
            cx,
            28,
            anchor="n",
            fill=TEXT_MUTED,
            font=("Trebuchet MS", 10, "bold"),
            text="EXIT",
        )
        self.canvas.create_oval(
            cx - r, cy - r, cx + r, cy + r, fill="#0f1a14", outline="#2a5c3a", width=2
        )

        if dist_tiles > 0:
            norm_r = dr / dist_tiles
            norm_c = dc / dist_tiles
            tip_x = cx + (r - 4) * norm_c
            tip_y = cy + (r - 4) * norm_r
            base_x = cx - 5 * norm_c
            base_y = cy - 5 * norm_r
            perp_x = -norm_r * 4
            perp_y = norm_c * 4
            self.canvas.create_polygon(
                tip_x,
                tip_y,
                base_x + perp_x,
                base_y + perp_y,
                base_x - perp_x,
                base_y - perp_y,
                fill="#67da86",
                outline="",
            )

        self.canvas.create_text(
            cx,
            cy + r + 6,
            anchor="n",
            fill="#67da86",
            font=("Trebuchet MS", 10, "bold"),
            text=f"{int(dist_tiles)}t",
        )

    def _draw_start_screen(self) -> None:
        self.canvas.create_rectangle(
            14,
            HUD_HEIGHT + 20,
            self.window_width - 14,
            self.window_height - 18,
            fill=PANEL,
            outline=PANEL_EDGE,
            width=2,
        )
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
        pulse = 0.65 + 0.35 * math.sin(self._now_ms() / 260.0)
        color = "#9de587" if pulse > 0.75 else "#77be68"
        self.canvas.create_text(
            self.window_width / 2,
            HUD_HEIGHT + 208,
            fill=color,
            font=("Trebuchet MS", 18, "bold"),
            text="\n\nPress any key or click to start",
        )

    def _draw_overlay(self, title: str, subtitle: str, footer: str) -> None:
        self.canvas.create_rectangle(
            20,
            HUD_HEIGHT + 50,
            self.window_width - 20,
            self.window_height - 50,
            fill="#12171d",
            outline=PANEL_EDGE,
            width=3,
        )
        self.canvas.create_text(
            self.window_width / 2,
            HUD_HEIGHT + 110,
            fill=TEXT,
            font=("Trebuchet MS", 24, "bold"),
            text=title,
        )
        self.canvas.create_text(
            self.window_width / 2,
            HUD_HEIGHT + 150,
            fill="#d3dbe5",
            font=("Trebuchet MS", 16, "bold"),
            text=subtitle,
        )
        self.canvas.create_text(
            self.window_width / 2,
            HUD_HEIGHT + 195,
            fill=TEXT_MUTED,
            font=("Trebuchet MS", 13),
            text=footer,
        )

    # ----------------------------------------------------------------- helpers

    def _get_camera_origin(self) -> tuple[int, int]:
        assert self.player is not None
        max_row = MAP_HEIGHT - VIEW_TILES
        max_col = MAP_WIDTH - VIEW_TILES
        row = max(0, min(max_row, self.player.row - VIEW_TILES // 2))
        col = max(0, min(max_col, self.player.col - VIEW_TILES // 2))
        return row, col

    def _is_walkable(self, row: int, col: int) -> bool:
        assert self.cave is not None
        return (
            0 <= row < MAP_HEIGHT
            and 0 <= col < MAP_WIDTH
            and self.cave.data[row, col] == 1
        )

    def _now_ms(self) -> float:
        return float(self.root.tk.call("clock", "milliseconds"))

    def run(self) -> None:
        self.update()
        self.root.mainloop()
