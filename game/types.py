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
    render_row: float = 0.0
    render_col: float = 0.0
    from_row: float = 0.0
    from_col: float = 0.0
    move_start_ms: float = 0.0

    def __post_init__(self) -> None:
        self.render_row = float(self.row)
        self.render_col = float(self.col)
        self.from_row = float(self.row)
        self.from_col = float(self.col)


@dataclass
class Item:
    kind: str
    row: int
    col: int


@dataclass
class BoidEnemy:
    row: int
    col: int
    alive: bool = True
    vel_row: float = 0.0
    vel_col: float = 0.0
    render_row: float = 0.0
    render_col: float = 0.0
    from_row: int = 0
    from_col: int = 0
