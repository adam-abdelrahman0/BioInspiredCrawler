from dataclasses import dataclass


@dataclass(frozen=True)
class EntityPlacement:
    player: tuple[int, int]
    sword: tuple[int, int]
    shield: tuple[int, int]
    coins: list[tuple[int, int]]
    food: list[tuple[int, int]]
    enemies: list[tuple[int, int]]
