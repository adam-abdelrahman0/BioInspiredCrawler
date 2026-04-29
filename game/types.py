from dataclasses import dataclass


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


@dataclass
class Player:
    row: int
    col: int
    facing: str = "down"


@dataclass
class Item:
    kind: str
    row: int
    col: int
