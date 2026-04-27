import numpy as np


class Grid:
    """Binary grid: 0 = wall, 1 = floor."""

    def __init__(self, data: np.ndarray):
        if data.dtype != np.uint8:
            data = data.astype(np.uint8)
        self.data = data

    @property
    def height(self) -> int:
        return self.data.shape[0]

    @property
    def width(self) -> int:
        return self.data.shape[1]

    @classmethod
    def random(
        cls, height: int, width: int, fill_prob: float, rng: np.random.Generator
    ) -> "Grid":
        """Initialize with floor cells at probability fill_prob."""
        data = (rng.random((height, width)) > fill_prob).astype(np.uint8)
        return cls(data)

    def neighbor_count(self, row: int, col: int) -> int:
        """Moore (8-neighbor) floor count; out-of-bounds treated as wall."""
        count = 0
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                r, c = row + dr, col + dc
                if 0 <= r < self.height and 0 <= c < self.width:
                    count += self.data[r, c]
        return count

    def copy(self) -> "Grid":
        return Grid(self.data.copy())

    def __repr__(self) -> str:
        cap = min(self.width, 40)
        lines = []
        for row in self.data:
            lines.append("".join("." if v else "#" for v in row[:cap]))
        if self.width > 40:
            lines[0] += f"  (+{self.width - 40} cols)"
        return "\n".join(lines)
