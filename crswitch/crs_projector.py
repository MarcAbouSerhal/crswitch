from pyproj import CRS, Transformer
from pyproj.transformer import TransformerGroup
from pyproj.exceptions import CRSError
from rasterio.transform import Affine
from shapely.geometry import Polygon

from typing import Any, Optional, Union, Iterable, List, Tuple, Self
import copy

from .util.helpers import generate_points, approximate_transform, interpolate_polygon

class Projector:
    def __init__(self, crs_from: Any, crs_to: Any, transformer: Optional[Transformer] = None):
        if not transformer:
            try:
                crs_from, crs_to = CRS.from_user_input(crs_from), CRS.from_user_input(crs_to)
                transformers = TransformerGroup(crs_from = crs_from, crs_to = crs_to, always_xy = True).transformers

                if not transformers:
                    raise CRSError("No transformer available.")
                
                self.transformer: Transformer = transformers[0]
            except:
                raise CRSError(
                    'crs_from and crs_to must have valid CRS formats, for example:\n'
                    'EPSG code as int: 4326\n'
                    'EPSG code as str: "EPSG:4326"\n'
                    'PROJ string: "+proj=longlat +datum=WGS84"\n'
                    'CRS instance: CRS.from_epsg(4326)'
                )
        else:
            self.transformer: Transformer = transformer
    
    @staticmethod
    def from_transformer(transformer: Transformer) -> Self:
        return Projector(None, None, transformer)
    
    def project_points(self, points: Iterable[Union[Tuple[float, float], List[float]]]) -> Iterable[Tuple[float, float]]:
        return [self.transformer.transform(x, y) for x, y in points]
    
    def project_point(self, x: float, y: float) -> Tuple[float, float]:
        return self.transformer.transform(x, y)
    
    def project_polygon(self, polygon: Iterable[Union[Tuple[float, float], List[float]]], interpolation: Optional[int] = None, self_closing: bool = False) -> List[Tuple[float, float]]:
        '''
        Projects a polygon in iterable format from the start CRS to the destination CRS

        Args:
            polygon (Iterable[Union[Tuple[float, float], List[float]]]): polygon in iterable format
            interpolation (int, optional): Number of points projected per line

        Returns:
            List[Tuple[float, float]]: projected polygon in list format
        '''
        return self.project_points(interpolate_polygon(polygon, interpolation, self_closing)) if interpolation else self.project_points(polygon)
    
    def project_shapely_polygon(self, polygon: Polygon, interpolation: Optional[int] = None) -> Polygon:
        """
        Projects a Shapely Polygon from the start CRS to the destination CRS

        Args:
            polygon (Polygon): Shapely Polygon
            interpolation (int, optional): Number of points projected per line

        Returns:
            Polygon: Projected Shapely Polygon
        """
        outer_coords = self.project_polygon(polygon.exterior.coords, interpolation, True)
        holes = [self.project_polygon(ring.coords, interpolation, True) for ring in polygon.interiors]
        return Polygon(outer_coords, holes = holes)
    
    def project_geojson_object(self, geojson: dict, interpolation: Optional[int] = None) -> dict:
        """
        Projects a GeoJSON object (`Point`, `MultiPoint`, `LineString`, `MultiLineString`, `Polygon`, `MultiPolygon` or `GeometryCollection`) from the start CRS to the destination CRS

        Args:
            geojson (dict): GeoJSON object
            interpolation (int, optional): Number of points projected per line (ignored if type if `Point`)

        Returns:
            dict: Projected GeoJSON object
        """
        new_geojson = {k: copy.deepcopy(v) for k, v in geojson.items() if k not in ['coordinates', 'geometries']} # no need to deep copy the coordinates
        geometry_type = geojson['type']
        if geometry_type == 'Point': new_geojson['coordinates'] = list(self.project_point(*geojson['coordinates']))
        elif geometry_type in ['MultiPoint', 'LineString']: new_geojson['coordinates'] = map(list, self.project_polygon(geojson['coordinates'], interpolation, True))
        elif geometry_type in ['MultiLineString', 'Polygon']: new_geojson['coordinates'] = [map(list, self.project_polygon(shape, interpolation, True)) for shape in geojson['coordinates']]
        elif geometry_type == 'MultiPolygon': new_geojson['coordinates'] = [[map(list, self.project_polygon(ring, interpolation, True)) for ring in polygon] for polygon in geojson['coordinates']]
        elif geometry_type == 'GeometryCollection': new_geojson['geometries'] = [self.project_geojson_object(geojson_object, interpolation, True) for geojson_object in geojson['geometries']]
        return new_geojson
    
    def project_transform(self, transform: Affine, points_from: Iterable[Union[Tuple[float, float], List[float]]]) -> Affine:
        """
        Computes the affine transformation that best maps points in `points_from` to coordinates in the destination CRS
        using a least squares approach

        This function first projects points in `points_to` to the start CRS using `transform` and then to the destination CRS using `transformer`
        and finally uses `approximate_transform` to find the best fitting transform

        Args:
            transform (Affine): affine geospatial transform that is being projected
            points_from (Iterable[Union[Tuple[float, float], List[float]]]): points of the grid for which the projected transform will best fit
        
        Returns:
            Affine: projected transform
        """
        points_to = self.project_points([transform * (x, y) for x, y in points_from])
        return approximate_transform(points_from, points_to)
    
    def project_transform_grid(self, transform: Affine, x_range: int, y_range: int, b: int = 3) -> Affine:
        """
        Computes the affine transformation that best maps points on the grid of size `x_range` * `y_range` to coordinates in the destination CRS
        using a least squares approach

        This function first chooses a point for every `b` * `b` square of the grid using `generate_points`, 
        and then projects those points to the start CRS using `transform` and then to the destination CRS using `transformer`
        and finally uses `approximate_transform` to find the best fitting transform

        Args:
            transform (Affine): affine geospatial transform that is being projected
            x_range (int): possible x values on the grid (0-indexed)
            y_range (int): possible y values on the grid (0-indexed)
            b (int, optional): block size used to choose points
        
        Returns:
            Affine: projected transform
        """
        return self.project_transform(transform, generate_points(x_range, y_range, b))