from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap

from .constants import (
    ITEM_COIN,
    ITEM_FOOD,
    ITEM_SHIELD,
    ITEM_SWORD,
    MAP_HEIGHT,
    MAP_WIDTH,
)


# PNG cave map export with colored markers and a legend.
def save_level_map_png(
    *,
    cave,
    player,
    exit_tile: tuple[int, int],
    items,
    enemies,
    swarm_enemies=(),
    level: int,
) -> Path:
    # Creates the output directory and chooses a stable filename for this level's map image.
    output_dir = Path("output")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"level_{level:03d}_map.png"

    # Draws the cave layout as a full-level overview image.
    fig, ax = plt.subplots(figsize=(12, 8), dpi=150)
    cave_cmap = ListedColormap(["#1c1f24", "#d7ddd8"])
    ax.imshow(
        cave.data,
        cmap=cave_cmap,
        origin="upper",
        interpolation="nearest",
    )

    player_handle = ax.scatter(
        player.col,
        player.row,
        s=42,
        c="#4d9fff",
        edgecolors="black",
        linewidths=0.4,
        label="Player",
        zorder=4,
    )
    exit_handle = ax.scatter(
        exit_tile[1],
        exit_tile[0],
        s=42,
        c="#36d97e",
        edgecolors="black",
        linewidths=0.4,
        label="Exit",
        zorder=4,
    )

    # Splits entities into marker groups so the legend can match the game objects clearly.
    sword_tiles = [(item.row, item.col) for item in items if item.kind == ITEM_SWORD]
    shield_tiles = [
        (item.row, item.col) for item in items if item.kind == ITEM_SHIELD
    ]
    food_tiles = [(item.row, item.col) for item in items if item.kind == ITEM_FOOD]
    coin_tiles = [(item.row, item.col) for item in items if item.kind == ITEM_COIN]
    enemy_tiles = [(enemy.row, enemy.col) for enemy in enemies if enemy.alive]
    swarm_tiles = [(enemy.row, enemy.col) for enemy in swarm_enemies if enemy.alive]

    legend_handles = [player_handle, exit_handle]

    # Plots one colored marker group and returns its legend handle when tiles exist.
    def plot_group(
        tiles: list[tuple[int, int]],
        color: str,
        label: str,
        size: int = 34,
    ):
        if not tiles:
            return None
        rows = [tile[0] for tile in tiles]
        cols = [tile[1] for tile in tiles]
        return ax.scatter(
            cols,
            rows,
            s=size,
            c=color,
            edgecolors="black",
            linewidths=0.35,
            label=label,
            zorder=4,
            
        )

    for handle in (
        plot_group(sword_tiles, "#e7eef7", "Sword"),
        plot_group(shield_tiles, "#7caee6", "Shield"),
        plot_group(food_tiles, "#044413", "Food"),
        plot_group(coin_tiles, "#e2b84b", "Coins"),
        plot_group(enemy_tiles, "#c74c4c", "Patrol Enemies"),
        plot_group(swarm_tiles, "#b76cff", "Swarm Enemies"),
    ):
        if handle is not None:
            legend_handles.append(handle)

    # Adds axes, grid, and legend information before saving the finished PNG.
    ax.set_title(f"Dungeon Crawler Level {level} Map", fontsize=14)
    ax.set_xlabel("Column")
    ax.set_ylabel("Row")
    ax.set_xticks(np.arange(0, MAP_WIDTH, 5))
    ax.set_yticks(np.arange(0, MAP_HEIGHT, 5))
    ax.grid(color="black", alpha=0.10, linewidth=0.5)
    ax.set_xlim(-0.5, MAP_WIDTH - 0.5)
    ax.set_ylim(MAP_HEIGHT - 0.5, -0.5)
    ax.legend(
        handles=legend_handles,
        loc="upper left",
        bbox_to_anchor=(1.02, 1.0),
        borderaxespad=0.0,
        frameon=True,
        title="Legend",
    )
    fig.tight_layout()
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)
    return output_path
