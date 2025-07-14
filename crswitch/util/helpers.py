from rasterio.transform import Affine

from typing import Iterable, Tuple

import numpy as np

def interpolate_polygon(polygon: Iterable[Tuple[float, float]], interpolation: int = 4, self_closing: bool = False) -> Iterable[Tuple[float, float]]:
    interpolated_polygon = []
    n = len(polygon) - int(self_closing)
    for idx in range(n):
        x_initial, y_initial = polygon[idx]
        x_next, y_next = polygon[(idx + 1) % n]
        x_diff = (x_next - x_initial) / interpolation
        y_diff = (y_next - y_initial) / interpolation
        for i in range(interpolation):
            interpolated_polygon.append((x_initial + i * x_diff, y_initial + i * y_diff))
    if self_closing: interpolated_polygon.append(polygon[0])
    return interpolated_polygon
    
def approximate_transform(points_from: Iterable[Tuple[float, float]], points_to: Iterable[Tuple[float, float]]) -> Affine:
    '''
    Finds the constants (a, b, c, d, e, f) of the affine transform that most closely maps points int points_from to points in points_to
    By computing the least squares solution to the following equation:
        | x_1 y_1 1 |   | a d |   | x'_1 y'_1 |
        | x_2 y_2 1 | . | b e | = | x'_2 y'_2 |
        | ......... |   | c f |   | ......... |
            A       .    x    =       b
    '''
    A = np.array([[x, y, 1] for (x, y) in points_from])
    b = np.array([[x, y] for (x, y) in points_to])
    x, _, _, _ = np.linalg.lstsq(A, b, rcond = None)
    return Affine(x[0, 0], x[1, 0], x[2, 0], x[0, 1], x[1, 1], x[2, 1])

def generate_points(x_range: int, y_range: int, b: int = 3) -> Iterable[Tuple[float, float]]:
    '''
    Given square with size x_range * y_range, and block size b
    Returns list of points, with each b x b subsquare being represented by a point
    '''
    x_s = [b * i + ((b - 1) // 2) for i in range(x_range // b)]
    if x_range % b != 0:
        x_s.append(b * (x_range // b) + max(b - 1, (x_range - 1) % b) // 2)
    y_s = [b * i + ((b - 1) // 2) for i in range(y_range // b)]
    if y_range % b != 0:
        y_s.append(b * (y_range // b) + max(b - 1, (x_range - 1) % b) // 2)
    return [(x, y) for x in x_s for y in y_s]