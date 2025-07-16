from rasterio.transform import Affine

from typing import Union, Iterable, List, Tuple

import numpy as np

def interpolate_polygon(polygon: Iterable[Union[Tuple[float, float], List[float]]], interpolation: int = 4, self_closing: bool = False) -> Iterable[Tuple[float, float]]:
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
    
def approximate_transform(points_from: Iterable[Union[Tuple[float, float], List[float]]], points_to: Iterable[Union[Tuple[float, float], List[float]]]) -> Tuple[float, float, float, float, float, float]:
    """
    Computes the affine transformation that best maps `points_from` to `points_to`
    using a least squares approach

    The function solves for the constants (a, b, c, d, e, f) in the affine transform: 

        x′ = a * x + b * y + c
        y′ = d * x + e * y + f

    by minimizing the squares error in the matrix equation:

        | x₁ y₁ 1 |       | a d |       | x′₁ y′₁ |
        | x₂ y₂ 1 |   .   | b e |   ≈   | x′₂ y′₂ |
        | ....... |       | c f |       | ....... |
             A               x               B

    Args:
        points_from (Iterable[Union[Tuple[float, float], List[float]]]): List of source (x, y) points.
        points_to (Iterable[Union[Tuple[float, float], List[float]]]): List of target (x', y') points.

    Returns:
        Tuple[float, float, float, float, float, float]: Coefficients (a, b, c, d, e, f) of the best-fit affine transformation.
    """
    A = np.array([[x, y, 1] for x, y in points_from])
    b = np.array([[x, y] for x, y in points_to])
    x, _, _, _ = np.linalg.lstsq(A, b, rcond = None)
    return (x[0, 0], x[1, 0], x[2, 0], x[0, 1], x[1, 1], x[2, 1])

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