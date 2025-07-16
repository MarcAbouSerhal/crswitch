from pyproj import CRS, Transformer
from pyproj.transformer import TransformerGroup
from pyproj.exceptions import CRSError
from rasterio import Affine
from shapely.geometry import Polygon

from typing import Any, Optional, Union, Iterable, List, Tuple, Self
import copy

from .util.helpers import generate_points, approximate_transform, interpolate_polygon

class Projector:
    def __init__(self, crs_from: Any, crs_to: Any, transformer: Optional[Transformer] = None):
        '''
        Creates `Projector` instance for transforming from `crs_from` to `crs_to`, or from an existing PyProj `Transformer` instance

        Args:
            crs_from (`Any`): Start CRS
            crs_to (`Any`): Destination CRS
            teansformer (`Transformer`, optional): Projector's internal transformer 

        Returns:
            `Projector`: New `Projector` instance
        '''
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
        '''
        Creates `Projector` instance from a PyProj `Transformer` instance

        Args:
            transformer (`Transformer`): Projector's internal transformer

        Returns:
            `Projector`: New `Projector` instance
        '''
        return Projector(None, None, transformer)
    
    def project_points(self, points: Iterable[Union[Tuple[float, float], List[float]]]) -> List[Tuple[float, float]]:
        '''
        Projects a list of points from the start CRS to the destination CRS
        
        Args:
            points (`Iterable[Union[Tuple[float, float], List[float]]]`): Points in the start CRS
    
        Returns:
            `List[Tuple[float, float]]`: Projected list of points
        '''
        return [self.transformer.transform(x, y) for x, y in points]
    
    def project_point(self, x: float, y: float) -> Tuple[float, float]:
        '''
        Projects a point (x, y) from the start CRS to the destination CRS

        Args:
            x (`float`): x coordinate of the point in the start CRS
            y (`float`): y coordinate of the point in the start CRS
        
        Returns:
            `Tuple[float, float]`: Projected point
        '''
        return self.transformer.transform(x, y)
    
    def project_polygon(self, polygon: Iterable[Union[Tuple[float, float], List[float]]], interpolation: Optional[int] = None, self_closing: bool = False) -> List[Tuple[float, float]]:
        '''
        Projects a polygon in iterable format from the start CRS to the destination CRS

        Args:
            polygon (`Iterable[Union[Tuple[float, float], List[float]]]`): Polygon in iterable format
            interpolation (`int`, optional): Number of points projected per line

        Returns:
            `List[Tuple[float, float]]`: Projected polygon
        '''
        return self.project_points(interpolate_polygon(polygon, interpolation, self_closing)) if interpolation else self.project_points(polygon)
    
    def project_shapely_polygon(self, polygon: Polygon, interpolation: Optional[int] = None) -> Polygon:
        """
        Projects a Shapely `Polygon` instance from the start CRS to the destination CRS

        Args:
            polygon (`Polygon`): Shapely Polygon
            interpolation (`int`, optional): Number of points projected per line

        Returns:
            `Polygon`: Projected polygon
        """
        outer_coords = self.project_polygon(polygon.exterior.coords, interpolation, True)
        holes = [self.project_polygon(ring.coords, interpolation, True) for ring in polygon.interiors]
        return Polygon(outer_coords, holes = holes)
    
    def project_geojson_object(self, geojson: dict, interpolation: Optional[int] = None) -> dict:
        """
        Projects a GeoJSON object (`Point`, `MultiPoint`, `LineString`, `MultiLineString`, `Polygon`, `MultiPolygon` or `GeometryCollection`) from the start CRS to the destination CRS

        Args:
            geojson (`dict`): GeoJSON object
            interpolation (`int`, optional): Number of points projected per line (ignored if type if `Point`)

        Returns:
            `dict`: Projected GeoJSON object
        """
        new_geojson = {k: copy.deepcopy(v) for k, v in geojson.items() if k not in ['coordinates', 'geometries']} # no need to deep copy the coordinates
        geometry_type = geojson['type']
        if geometry_type == 'Point': new_geojson['coordinates'] = list(self.project_point(*geojson['coordinates']))
        elif geometry_type in ['MultiPoint', 'LineString']: new_geojson['coordinates'] = map(list, self.project_polygon(geojson['coordinates'], interpolation, True))
        elif geometry_type in ['MultiLineString', 'Polygon']: new_geojson['coordinates'] = [map(list, self.project_polygon(shape, interpolation, True)) for shape in geojson['coordinates']]
        elif geometry_type == 'MultiPolygon': new_geojson['coordinates'] = [[map(list, self.project_polygon(ring, interpolation, True)) for ring in polygon] for polygon in geojson['coordinates']]
        elif geometry_type == 'GeometryCollection': new_geojson['geometries'] = [self.project_geojson_object(geojson_object, interpolation, True) for geojson_object in geojson['geometries']]
        return new_geojson

    def project_tuple_transform(self, transform: Tuple[float, float, float, float, float ,float], points_from: Iterable[Union[Tuple[float, float], List[float]]]) -> Tuple[float, float, float, float, float, float]:
        """
        Computes the affine transformation that best maps points in `points_from` to coordinates in the destination CRS
        using a least squares approach

        This function first projects points in `points_to` to the start CRS using `transform` and then to the destination CRS using `transformer`
        and finally uses `approximate_transform` to find the best fitting transform

        Args:
            transform (`Tuple[float, float, float, float, float ,float]`): Coefficients (a, b, c, d, e, f) of the affine geospatial transform that is being projected
            points_from (`Iterable[Union[Tuple[float, float], List[float]]]`): Points of the grid for which the projected transform will best fit
        
        Returns:
            `Tuple[float, float, float, float, float ,float]`: Projected transform
        """
        a, b, c, d, e, f = transform
        points_to = self.project_points([(a * x + b * y + c, d * x + e * y + f) for x, y in points_from])
        return approximate_transform(points_from, points_to)
    
    def project_tuple_transform_grid(self, transform: Tuple[float, float, float, float, float ,float], x_range: int, y_range: int, b: int = 3) -> Tuple[float, float, float, float, float ,float]:
        """
        Computes the affine transformation that best maps points on the grid of size `x_range` * `y_range` to coordinates in the destination CRS
        using a least squares approach

        This function first chooses a point for every `b` * `b` square of the grid using `generate_points`, 
        and then projects those points to the start CRS using `transform` and then to the destination CRS using `transformer`
        and finally uses `approximate_transform` to find the best fitting transform

        Args:
            transform (`Tuple[float, float, float, float, float ,float]`): Coefficients (a, b, c, d, e, f) of the affine geospatial transform that is being projected
            x_range (`int`): Possible x values on the grid (0-indexed)
            y_range (`int`): Possible y values on the grid (0-indexed)
            b (`int`, optional): Block size used to choose points
        
        Returns:
            `Tuple[float, float, float, float, float ,float]`: Projected transform
        """
        return self.project_tuple_transform(transform, generate_points(x_range, y_range, b))
    
    def project_affine_transform(self, transform: Affine, points_from: Iterable[Union[Tuple[float, float], List[float]]]) -> Affine:
        """
        Computes the affine transformation that best maps points in `points_from` to coordinates in the destination CRS
        using a least squares approach

        This function first projects points in `points_to` to the start CRS using `transform` and then to the destination CRS using `transformer`
        and finally uses `approximate_transform` to find the best fitting transform

        Args:
            transform (`Affine`): Affine geospatial transform that is being projected
            points_from (`Iterable[Union[Tuple[float, float], List[float]]]`): Points of the grid for which the projected transform will best fit
        
        Returns:
            `Affine`: Projected transform
        """
        points_to = self.project_points([transform * (x, y) for x, y in points_from])
        return Affine(*approximate_transform(points_from, points_to))
    
    def project_affine_transform_grid(self, transform: Affine, x_range: int, y_range: int, b: int = 3) -> Affine:
        """
        Computes the affine transformation that best maps points on the grid of size `x_range` * `y_range` to coordinates in the destination CRS
        using a least squares approach

        This function first chooses a point for every `b` * `b` square of the grid using `generate_points`, 
        and then projects those points to the start CRS using `transform` and then to the destination CRS using `transformer`
        and finally uses `approximate_transform` to find the best fitting transform

        Args:
            transform (`Affine`): Affine geospatial transform that is being projected
            x_range (`int`): Possible x values on the grid (0-indexed)
            y_range (`int`): Possible y values on the grid (0-indexed)
            b (`int`, optional): Block size used to choose points
        
        Returns:
            `Affine`: Projected transform
        """
        return self.project_affine_transform(transform, generate_points(x_range, y_range, b))