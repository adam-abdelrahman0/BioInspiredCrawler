import math
import tkinter as tk

from .constants import (
    FLOOR_A,
    FLOOR_B,
    GOLD,
    HEART,
    PANEL_EDGE,
    TILE_SIZE,
    WALL_A,
    WALL_B,
    WALL_C,
)


def draw_floor(canvas: tk.Canvas, x: int, y: int, row: int, col: int, tag: str = "") -> None:
    base = FLOOR_A if (row + col) % 2 == 0 else FLOOR_B
    canvas.create_rectangle(x, y, x + TILE_SIZE, y + TILE_SIZE, fill=base, width=0, tags=tag)
    canvas.create_line(x + 4, y + 8, x + 12, y + 8, fill="#5a636d", width=2, tags=tag)
    canvas.create_line(x + 18, y + 15, x + 24, y + 13, fill="#5a636d", width=2, tags=tag)
    canvas.create_line(x + 10, y + 25, x + 12, y + 21, fill="#5a636d", width=2, tags=tag)


def draw_wall(canvas: tk.Canvas, x: int, y: int, row: int, col: int, tag: str = "") -> None:
    canvas.create_rectangle(x, y, x + TILE_SIZE, y + TILE_SIZE, fill=WALL_A, width=0, tags=tag)
    canvas.create_rectangle(x, y + 22, x + TILE_SIZE, y + TILE_SIZE, fill=WALL_C, width=0, tags=tag)
    canvas.create_rectangle(x + 2, y + 4, x + 12, y + 12, fill=WALL_B, width=0, tags=tag)
    canvas.create_rectangle(x + 14, y + 3, x + 28, y + 11, fill=WALL_B, width=0, tags=tag)
    if (row + col) % 2 == 0:
        canvas.create_rectangle(x + 5, y + 16, x + 13, y + 20, fill="#313945", width=0, tags=tag)
    else:
        canvas.create_rectangle(x + 18, y + 16, x + 27, y + 20, fill="#313945", width=0, tags=tag)


def draw_player(canvas: tk.Canvas, x: int, y: int, facing: str, tag: str = "") -> None:
    canvas.create_rectangle(x + 8, y + 10, x + 24, y + 24, fill="#5f8fda", outline="", tags=tag)
    canvas.create_rectangle(x + 9, y + 4, x + 23, y + 10, fill="#d8e6ff", outline="", tags=tag)
    canvas.create_rectangle(x + 10, y + 11, x + 13, y + 14, fill="#11151a", outline="", tags=tag)
    canvas.create_rectangle(x + 19, y + 11, x + 22, y + 14, fill="#11151a", outline="", tags=tag)
    canvas.create_rectangle(x + 13, y + 17, x + 19, y + 19, fill="#d4ae7c", outline="", tags=tag)
    canvas.create_rectangle(x + 10, y + 24, x + 14, y + 30, fill="#294a7f", outline="", tags=tag)
    canvas.create_rectangle(x + 18, y + 24, x + 22, y + 30, fill="#294a7f", outline="", tags=tag)
    if facing == "up":
        canvas.create_polygon(x + 16, y + 1, x + 11, y + 6, x + 21, y + 6, fill="#d8e6ff", outline="", tags=tag)
    elif facing == "down":
        canvas.create_polygon(x + 16, y + 31, x + 11, y + 26, x + 21, y + 26, fill="#d8e6ff", outline="", tags=tag)
    elif facing == "left":
        canvas.create_polygon(x + 1, y + 16, x + 6, y + 11, x + 6, y + 21, fill="#d8e6ff", outline="", tags=tag)
    else:
        canvas.create_polygon(x + 31, y + 16, x + 26, y + 11, x + 26, y + 21, fill="#d8e6ff", outline="", tags=tag)


def draw_enemy(canvas: tk.Canvas, x: int, y: int, tag: str = "") -> None:
    canvas.create_rectangle(x + 6, y + 11, x + 26, y + 22, fill="#b84242", outline="", tags=tag)
    canvas.create_rectangle(x + 8, y + 5, x + 24, y + 11, fill="#b84242", outline="", tags=tag)
    canvas.create_polygon(x + 7, y + 7, x + 10, y + 2, x + 12, y + 7, fill="#efb06a", outline="", tags=tag)
    canvas.create_polygon(x + 25, y + 7, x + 22, y + 2, x + 20, y + 7, fill="#efb06a", outline="", tags=tag)
    canvas.create_rectangle(x + 10, y + 10, x + 13, y + 13, fill="#130505", outline="", tags=tag)
    canvas.create_rectangle(x + 19, y + 10, x + 22, y + 13, fill="#130505", outline="", tags=tag)
    canvas.create_rectangle(x + 10, y + 22, x + 14, y + 29, fill="#7e2323", outline="", tags=tag)
    canvas.create_rectangle(x + 18, y + 22, x + 22, y + 29, fill="#7e2323", outline="", tags=tag)


def draw_sword(canvas: tk.Canvas, x: int, y: int, tag: str = "") -> None:
    blade = "#c7cfd8"
    edge = "#ebf2fa"
    hilt = "#9b6a2d"
    canvas.create_rectangle(x + 15, y + 4, x + 17, y + 21, fill=blade, outline="", tags=tag)
    canvas.create_rectangle(x + 14, y + 3, x + 18, y + 7, fill=edge, outline="", tags=tag)
    canvas.create_rectangle(x + 12, y + 18, x + 20, y + 21, fill=hilt, outline="", tags=tag)
    canvas.create_rectangle(x + 14, y + 21, x + 18, y + 28, fill="#6f4922", outline="", tags=tag)


def draw_shield(canvas: tk.Canvas, x: int, y: int, tag: str = "") -> None:
    outer = "#35537c"
    inner = "#79a7d5"
    shine = "#d8e7fb"
    canvas.create_polygon(
        x + 16, y + 4, x + 25, y + 10, x + 22, y + 25, x + 16, y + 29, x + 10, y + 25, x + 7, y + 10,
        fill=outer, outline="", tags=tag,
    )
    canvas.create_polygon(
        x + 16, y + 7, x + 22, y + 11, x + 20, y + 23, x + 16, y + 26, x + 12, y + 23, x + 10, y + 11,
        fill=inner, outline="", tags=tag,
    )
    canvas.create_line(x + 16, y + 10, x + 16, y + 23, fill=shine, width=2, tags=tag)
    canvas.create_line(x + 12, y + 16, x + 20, y + 16, fill=shine, width=2, tags=tag)


def draw_food(canvas: tk.Canvas, x: int, y: int, tag: str = "") -> None:
    canvas.create_oval(x + 8, y + 8, x + 23, y + 22, fill="#c74545", outline="", tags=tag)
    canvas.create_rectangle(x + 14, y + 5, x + 17, y + 9, fill="#6d3f1d", outline="", tags=tag)
    canvas.create_oval(x + 16, y + 4, x + 24, y + 10, fill="#5da85b", outline="", tags=tag)
    canvas.create_oval(x + 10, y + 12, x + 13, y + 15, fill="#fbb9b9", outline="", tags=tag)


def draw_coin(canvas: tk.Canvas, x: int, y: int, tag: str = "") -> None:
    canvas.create_oval(x + 10, y + 7, x + 22, y + 24, fill="#9a6d1d", outline="", tags=tag)
    canvas.create_oval(x + 12, y + 8, x + 20, y + 23, fill=GOLD, outline="", tags=tag)
    canvas.create_line(x + 16, y + 11, x + 16, y + 20, fill="#fff1ab", width=2, tags=tag)


def draw_exit(canvas: tk.Canvas, x: int, y: int, now_ms: float, tag: str = "") -> None:
    pulse = 2 + 1.5 * math.sin(now_ms / 180.0)
    canvas.create_oval(
        x + 4 - pulse, y + 4 - pulse, x + 28 + pulse, y + 28 + pulse,
        fill="#193223", outline="#2ef07a", width=2, tags=tag,
    )
    canvas.create_oval(x + 8, y + 8, x + 24, y + 24, fill="#67da86", outline="", tags=tag)
    canvas.create_oval(x + 12, y + 12, x + 20, y + 20, fill="#d2ffe0", outline="", tags=tag)


def draw_heart_icon(canvas: tk.Canvas, x: int, y: int) -> None:
    canvas.create_oval(x, y, x + 10, y + 10, fill=HEART, outline="")
    canvas.create_oval(x + 8, y, x + 18, y + 10, fill=HEART, outline="")
    canvas.create_polygon(x - 1, y + 7, x + 9, y + 20, x + 19, y + 7, fill=HEART, outline="")


def draw_star_icon(canvas: tk.Canvas, x: int, y: int) -> None:
    canvas.create_polygon(
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
        outline="",
    )
