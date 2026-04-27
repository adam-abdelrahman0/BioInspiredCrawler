import argparse

import matplotlib.pyplot as plt
import numpy as np
import yaml

from ca import Grid, apply_rule, flood_fill_largest

# CA rule sets B5678/S45678
# CAVE vs SMOOTH-- cave is generated with rough edges and smoothing happens with flood fill
CAVE_BORN = frozenset({5, 6, 7, 8})
CAVE_SURVIVE = frozenset({4, 5, 6, 7, 8})
SMOOTH_BORN = frozenset({5, 6, 7, 8})
SMOOTH_SURVIVE = frozenset({5, 6, 7, 8})


def load_config(path: str = "config.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def parse_args(defaults: dict) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="CA cave generator")
    p.add_argument("--seed", type=int, default=None, help="RNG seed")
    p.add_argument(
        "--width", type=int, default=defaults.get("width", 80), help="Grid width"
    )
    p.add_argument(
        "--height", type=int, default=defaults.get("height", 50), help="Grid height"
    )
    p.add_argument(
        "--fill-prob",
        type=float,
        default=defaults.get("fill_prob", 0.45),
        help="Initial floor probability",
    )
    p.add_argument("--config", type=str, default="config.yaml", help="Config file path")
    return p.parse_args()


def print_summary(_raw: Grid, final: Grid, num_regions: int) -> None:
    total = final.height * final.width
    floor = int(final.data.sum())
    print("\n=== CA Cave Generation Summary ===")
    print(f"  Grid dimensions   : {final.width} x {final.height}")
    print(f"  Total floor cells : {floor}")
    print(f"  Floor percentage  : {floor / total * 100:.1f}%")
    print(f"  Disconnected regions before flood fill: {num_regions}")
    print("==================================\n")


def visualize(raw: Grid, final: Grid) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle("BioInspiredCrawler — CA Cave Generation", fontsize=13)

    axes[0].imshow(raw.data, cmap="binary", interpolation="nearest")
    axes[0].set_title("Raw cave (after CA)")
    axes[0].axis("off")

    axes[1].imshow(final.data, cmap="binary", interpolation="nearest")
    axes[1].set_title("Cleaned cave (after flood fill)")
    axes[1].axis("off")

    plt.tight_layout()
    plt.savefig("output/ca_cave.png", dpi=150, bbox_inches="tight")
    print("Figure saved to output/ca_cave.png")
    plt.show()


def run_ca_pipeline(
    height: int,
    width: int,
    fill_prob: float,
    ca_iterations: int,
    smooth_iterations: int,
    rng: np.random.Generator,
) -> tuple[Grid, Grid, int]:

    grid = Grid.random(height, width, fill_prob, rng)
    grid = apply_rule(grid, CAVE_BORN, CAVE_SURVIVE, ca_iterations)

    raw = grid.copy()

    grid = apply_rule(grid, SMOOTH_BORN, SMOOTH_SURVIVE, smooth_iterations)
    final, num_regions = flood_fill_largest(grid)

    return raw, final, num_regions


def main() -> None:
    cfg = load_config()
    args = parse_args(cfg)

    seed = args.seed if args.seed is not None else np.random.SeedSequence().entropy
    rng = np.random.default_rng(seed)
    print(f"Seed: {seed}")

    ca_iters = cfg.get("ca_iterations", 4)
    smooth_iters = cfg.get("smooth_iterations", 2)

    raw, final, num_regions = run_ca_pipeline(
        height=args.height,
        width=args.width,
        fill_prob=args.fill_prob,
        ca_iterations=ca_iters,
        smooth_iterations=smooth_iters,
        rng=rng,
    )

    print_summary(raw, final, num_regions)
    print(repr(final))
    visualize(raw, final)


if __name__ == "__main__":
    main()
