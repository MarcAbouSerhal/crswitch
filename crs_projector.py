from pyproj import CRS, Transformer
from pyproj.transformer import TransformerGroup
from pyproj.exceptions import CRSError

from typing import Any, Optional, Generator, Iterable, Tuple

from rasterio.transform import Affine

import numpy as np

class CRSProjector:
    def __init__(self, crs_from: Any, crs_to: Any):
        try:
            crs_from, crs_to = CRS.from_user_input(crs_from), CRS.from_user_input(crs_to)
            transformers = TransformerGroup(crs_from, crs_to, always_xy = True)

            if not transformers.has_transformers:
                raise CRSError("No transformer available.")
            
            self.transformer: Transformer = transformers.best_available
            self.crs_from: CRS = crs_from
            self.crs_to: CRS = crs_to
        except:
            raise CRSError(
                'crs_from and crs_to must have valid CRS formats, for example:\n'
                'EPSG code as int: 4326\n'
                'EPSG code as str: "EPSG:4326"\n'
                'PROJ string: "+proj=longlat +datum=WGS84"\n'
                'CRS instance: CRS.from_epsg(4326)'
            )
        
    @staticmethod
    def interpolate_polygon(polygon: Iterable[Tuple[float, float]], interpolation: int = 4) -> Iterable[Tuple[float, float]]:
        interpolated_polygon = []
        n = len(polygon)
        for idx in range(n):
            x_initial, y_initial = polygon[idx]
            x_next, y_next = polygon[(idx + 1) % n]
            x_diff = (x_next - x_initial) / interpolation
            y_diff = (y_next - y_initial) / interpolation
            for i in range(interpolation):
                interpolated_polygon.append((x_initial + i * x_diff, y_initial + i * y_diff))
        return interpolated_polygon
    
    def project_points(self, points: Iterable[Tuple[float, float]]) -> Generator[Tuple[float, float], None, None]:
        return self.transformer.itransform(points)
    
    def project_point(self, point: Tuple[float, float]) -> Tuple[float, float]:
        return self.transformer.transform(point)
    
    def project_polygon(self, polygon: Iterable[Tuple[float, float]], interpolation: Optional[int] = None) -> Generator[Tuple[float, float], None, None]:
        if interpolation: return self.project_point(CRSProjector.interpolate_polygon(polygon, interpolation))
        return self.project_points(polygon)
    
    @staticmethod
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
    
    @staticmethod
    def generate_points(x_range: int, y_range: int, b: int = 3) -> Iterable[Tuple[float, float]]:
        '''
        Given square with size x_range * y_range, and block size b
        Returns list of points, with each b x b subsquare being represented by a point
        '''
        x_s = [b * i + ((b - 1) // 2) for i in range(x_range // b)]
        if x_range % b != 0:
            x_s.append(b * (x_range // b) + max((b - 1) // 2, (x_range - 1) % b))
        y_s = [b * i + ((b - 1) // 2) for i in range(y_range // b)]
        if y_range % b != 0:
            y_s.append(b * (y_range // b) + max((b - 1) // 2, (x_range - 1) % b))
        return [(x, y) for x in x_s for y in y_s]
    
    def project_transform_custom(self, transform: Affine, points_from: Iterable[Tuple[float, float]]) -> Affine:
        coordinates = [transform * (x, y) for (x, y) in points_from]
        points_to = self.project_points(coordinates)
        return CRSProjector.approximate_transform(points_from, points_to)
    
    def project_transform(self, transform: Affine, x_range: int, y_range: int, b: int = 3) -> Affine:
        points_from = CRSProjector.generate_points(x_range, y_range, b)
        return self.project_transform_custom(transform, points_from)