def chebyshev(a: tuple[int, int], b: tuple[int, int]) -> int:
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def is_clear_of_neighbors(
    cell: tuple[int, int], occupied: set[tuple[int, int]], min_chebyshev: int = 1
) -> bool:
    for other in occupied:
        if chebyshev(cell, other) <= min_chebyshev:
            return False
    return True
