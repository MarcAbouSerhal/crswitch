from pyproj import CRS, Transformer
from pyproj.transformer import TransformerGroup
from pyproj.exceptions import CRSError
from rasterio.transform import Affine
from shapely.geometry import Polygon

from typing import Any, Optional, Iterable, Tuple
import copy

from .util.helpers import generate_points, approximate_transform, interpolate_polygon

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
    
    def project_points(self, points: Iterable[Tuple[float, float]]) -> Iterable[Tuple[float, float], None, None]:
        return [self.transformer.transform(point) for point in points]
    
    def project_point(self, point: Tuple[float, float]) -> Tuple[float, float]:
        return self.transformer.transform(point)
    
    def project_polygon(self, polygon: Iterable[Tuple[float, float]], interpolation: Optional[int] = None, self_closing: bool = False) -> Iterable[Tuple[float, float], None, None]:
        if interpolation: return self.project_points(interpolate_polygon(polygon, interpolation, self_closing))
        return self.project_points(polygon)
    
    def project_shapely_polygon(self, polygon: Polygon, interpolation: Optional[int] = None) -> Polygon:
        outer_coords = list(polygon.exterior.coords)
        holes = [list(ring.coords) for ring in polygon.interiors]
        outer_coords = self.project_polygon(outer_coords, interpolation, True)
        holes = [self.project_polygon(hole, interpolation, True) for hole in holes]
        return Polygon(outer_coords, holes = holes)
    
    def project_geojson_polygon(self, polygon: dict, interpolation: Optional[int] = None) -> dict:
        new_polygon = {k: copy.deepcopy(v) for k, v in polygon.items() if k != 'coordinates'} # no need to deep copy the coordinates
        new_polygon['coordinates'] = [self.project_polygon(ring, interpolation, True) for ring in polygon['coordinates']]
        return new_polygon
    
    def project_transform_custom(self, transform: Affine, points_from: Iterable[Tuple[float, float]]) -> Affine:
        coordinates = [transform * (x, y) for (x, y) in points_from]
        points_to = self.project_points(coordinates)
        return approximate_transform(points_from, points_to)
    
    def project_transform(self, transform: Affine, x_range: int, y_range: int, b: int = 3) -> Affine:
        points_from = generate_points(x_range, y_range, b)
        return self.project_transform_custom(transform, points_from)