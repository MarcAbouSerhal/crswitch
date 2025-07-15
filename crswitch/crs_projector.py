from pyproj import CRS, Transformer
from pyproj.transformer import TransformerGroup
from pyproj.exceptions import CRSError
from rasterio.transform import Affine
from shapely.geometry import Polygon

from typing import Any, Optional, Union, Iterable, List, Tuple
import copy

from .util.helpers import generate_points, approximate_transform, interpolate_polygon

class CRSProjector:
    def __init__(self, crs_from: Any, crs_to: Any):
        try:
            crs_from, crs_to = CRS.from_user_input(crs_from), CRS.from_user_input(crs_to)
            transformers = TransformerGroup(crs_from = crs_from, crs_to = crs_to, always_xy = True).transformers

            if not transformers:
                raise CRSError("No transformer available.")
            
            self.transformer: Transformer = transformers[0]
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
    
    def project_points(self, points: Iterable[Union[Tuple[float, float], List[float]]]) -> Iterable[Tuple[float, float]]:
        return [self.transformer.transform(x, y) for x, y in points]
    
    def project_point(self, x: float, y: float) -> Tuple[float, float]:
        return self.transformer.transform(x, y)
    
    def project_polygon(self, polygon: Iterable[Union[Tuple[float, float], List[float]]], interpolation: Optional[int] = None, self_closing: bool = False) -> Iterable[Tuple[float, float]]:
        return self.project_points(interpolate_polygon(polygon, interpolation, self_closing)) if interpolation else self.project_points(polygon)
    
    def project_shapely_polygon(self, polygon: Polygon, interpolation: Optional[int] = None) -> Polygon:
        outer_coords = self.project_polygon(polygon.exterior.coords, interpolation, True)
        holes = [self.project_polygon(ring.coords, interpolation, True) for ring in polygon.interiors]
        return Polygon(outer_coords, holes = holes)
    
    def project_geojson_object(self, polygon: dict, interpolation: Optional[int] = None) -> dict:
        new_polygon = {k: copy.deepcopy(v) for k, v in polygon.items() if k not in ['coordinates', 'geometries']} # no need to deep copy the coordinates
        geometry_type = polygon['type']
        if geometry_type == 'Point': new_polygon['coordinates'] = list(self.project_point(*polygon['coordinates']))
        elif geometry_type in ['MultiPoint', 'LineString']: new_polygon['coordinates'] = map(list, self.project_polygon(polygon['coordinates'], interpolation, True))
        elif geometry_type in ['MultiLineString', 'Polygon']: new_polygon['coordinates'] = [map(list, self.project_polygon(shape, interpolation, True)) for shape in polygon['coordinates']]
        elif geometry_type == 'MultiPolygon': new_polygon['coordinates'] = [[map(list, self.project_polygon(ring, interpolation, True)) for ring in polygon] for polygon in polygon['coordinates']]
        elif geometry_type == 'GeometryCollection': new_polygon['geometries'] = [self.project_geojson_object(geojson_object, interpolation, True) for geojson_object in polygon['geometries']]
        return new_polygon
    
    def project_transform_custom(self, transform: Affine, points_from: Iterable[Tuple[float, float]]) -> Affine:
        """
        Computes the affine transformation that best maps points in `points_from` to coordinates in `crs_to` 
        using a least squares approach

        This function first projects points in `points_to` to `crs_from` using `transform` and then to `crs_to` using `transformer`
        and finally uses `approximate_transform` to find the best fitting transform

        Args:
            transform (Affine): affine geospatial transform that is being projected
            points_from (Iterable[Tuple[float, float]]): points of the grid for which the projected transform will best fit
        
        Returns:
            Affine: projected transform
        """
        points_to = self.project_points([transform * (x, y) for (x, y) in points_from])
        return approximate_transform(points_from, points_to)
    
    def project_transform(self, transform: Affine, x_range: int, y_range: int, b: int = 3) -> Affine:
        """
        Computes the affine transformation that best maps points on the grid of size `x_range` * `y_range` to coordinates in `crs_to` 
        using a least squares approach

        This function first chooses a point for every `b` * `b` square of the grid using `generate_points`, 
        and then projects those points to `crs_from` using `transform` and then to `crs_to` using `transformer`
        and finally uses `approximate_transform` to find the best fitting transform

        Args:
            transform (Affine): affine geospatial transform that is being projected
            x_range (int): possible x values on the grid (0-indexed)
            y_range (int): possible y values on the grid (0-indexed)
            b (int, optional): block size used to choose points
        
        Returns:
            Affine: projected transform
        """
        return self.project_transform_custom(transform, generate_points(x_range, y_range, b))