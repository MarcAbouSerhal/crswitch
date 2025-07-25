from pyproj import CRS, Transformer
from pyproj.transformer import TransformerGroup
from pyproj.exceptions import CRSError
from rasterio import Affine
import shapely.geometry


from typing import Any, Optional, Union, Iterable, List, Tuple, Callable
import copy

from .util.helpers import generate_points, approximate_transform, interpolate_polygon

class Projector:
    def __init__(
        self, 
        crs_from: Any = None,
        crs_to: Any = None, 
        project_function: Optional[Callable[[float, float], Tuple[float, float]]] = None
    ):
        '''
        Creates `Projector` instance for projecting from `crs_from` to `crs_to`, or using an existing 'project_point' function

        Args:
            `crs_from` (`Any`, optional): Start CRS
            `crs_to` (`Any`, optional): Destination CRS
            `project_function` (`Callable[[float, float], Tuple[float, float]]`, optional): Projector's internal project function (if passed, `crs_from` and `crs_to` are ignored)
        '''
        if not project_function:
            try:
                crs_from, crs_to = CRS.from_user_input(crs_from), CRS.from_user_input(crs_to)
                transformers = TransformerGroup(crs_from = crs_from, crs_to = crs_to, always_xy = True).transformers

                if not transformers:
                    raise CRSError("No transformer available.")
                
                self._project_point: Callable[[float, float], Tuple[float, float]] = transformers[0].transform
            except:
                raise CRSError(
                    'crs_from and crs_to must have valid CRS formats, for example:\n'
                    'EPSG code as int: 4326\n'
                    'EPSG code as str: "EPSG:4326"\n'
                    'PROJ string: "+proj=longlat +datum=WGS84"\n'
                    'CRS instance: CRS.from_epsg(4326)'
                )
        else:
            assert isinstance(project_function, Callable), \
                "Project function must take two float arguments and return a tuple of two floats."
            self._project_point: Callable[[float, float], Tuple[float, float]] = project_function

    @classmethod
    def from_pyproj_transformer(
        transformer: Transformer
    ):
        '''
        Creates `Projector` instance using an existing PyProj `Transformer` instance

        Args:
            `transformer` (`Transformer`, optional): `Transformer` instance whose `transform` function will be used as Projector's internal project function

        Returns:
            `Projector`: `Projector` instance that uses `transformer.transform` as its internal project function
        '''
        return Projector(project_function = transformer.transform)
    
    @classmethod
    def from_affine_transform(
        transform: Affine
    ):
        '''
        Creates `Projector` instance using an existing `Affine` transform

        Args:
            `transform` (`Affine`, optional): `Affine` transform will be used as Projector's internal project function

        Returns:
            `Projector`: `Projector` instance that uses `transform` as its internal project function
        '''
        return Projector(project_function = lambda x, y: transform * (x, y))

    @property
    def project_point(
        self
    ) -> Callable[[float, float], Tuple[float, float]]:
        return self._project_point
    
    @project_point.setter
    def project_point(
        self,
        new_project_point: Callable[[float, float], Tuple[float, float]]
    ) -> None:
        assert isinstance(project_function, Callable), \
            "Project function must take two float arguments and return a tuple of two floats."
        self._project_point = new_project_point
    
    def project_points(
        self, 
        points: Iterable[Union[Tuple[float, float], List[float]]]
    ) -> List[Tuple[float, float]]:
        '''
        Projects a list of points from the start CRS to the destination CRS
        
        Args:
            `points` (`Iterable[Union[Tuple[float, float], List[float]]]`): Points in the start CRS
    
        Returns:
            `List[Tuple[float, float]]`: Projected list of points
        '''
        return [self._project_point(x, y) for x, y in points]
    
    def project_polygon(
        self, 
        polygon: Iterable[Union[Tuple[float, float], List[float]]], 
        interpolation: Optional[int] = None, 
        self_closing: bool = False
    ) -> List[Tuple[float, float]]:
        '''
        Projects a polygon in iterable format from the start CRS to the destination CRS

        Args:
            `polygon` (`Iterable[Union[Tuple[float, float], List[float]]]`): Polygon in iterable format
            `interpolation` (`int`, optional): Number of points projected per segment
            `self_closing` (`bool`, optional): Whether the polygon is self-closing i.e. `polygon[0] == polygon[-1]`

        Returns:
            `List[Tuple[float, float]]`: Projected polygon
        '''
        return self.project_points(interpolate_polygon(polygon, interpolation, self_closing)) if interpolation else self.project_points(polygon)

    def project_line(self, line: Iterable[Union[Tuple[float, float], List[float]]], interpolation: Optional[int] = None) -> List[Tuple[float, float]]:
        '''
        Projects a line in iterable format from the start CRS to the destination CRS

        Args:
            line (`Iterable[Union[Tuple[float, float], List[float]]]`): Polygon in iterable format
            interpolation (`int`, optional): Number of points projected per segment

        Returns:
            `List[Tuple[float, float]]`: Projected line
        '''
        return self.project_polygon(line, interpolation, True)

    def project_shapely_object(
        self, 
        shapely_object: Union[shapely.geometry.Point, shapely.geometry.LineString, shapely.geometry.LinearRing, shapely.geometry.Polygon, shapely.geometry.MultiPoint, shapely.geometry.MultiLineString, shapely.geometry.MultiPolygon, shapely.geometry.GeometryCollection], 
        interpolation: Optional[int] = None
    ) ->  Union[shapely.geometry.Point, shapely.geometry.LineString, shapely.geometry.LinearRing, shapely.geometry.Polygon, shapely.geometry.MultiPoint, shapely.geometry.MultiLineString, shapely.geometry.MultiPolygon, shapely.geometry.GeometryCollection]:
        """
        Projects a Shapely object (`Point`, `LineString`, `LinearRing`, `Polygon`, `MultiPoint`, `MultiLineString`, `MultiPolygon`, `GeometryCollection`) 
        from the start CRS to the destination CRS

        Args:
            `shapely_object` (`Union[shapely.geometry.Point, shapely.geometry.LineString, shapely.geometry.LinearRing, shapely.geometry.Polygon, shapely.geometry.MultiPoint, shapely.geometry.MultiLineString, shapely.geometry.MultiPolygon, shapely.geometry.GeometryCollection]`): Shapely object
            `interpolation` (`int`, optional): Number of points projected per line (ignored if type is `Point`)

        Returns:
            `Union[shapely.geometry.Point, shapely.geometry.LineString, shapely.geometry.LinearRing, shapely.geometry.Polygon, shapely.geometry.MultiPoint, shapely.geometry.MultiLineString, shapely.geometry.MultiPolygon, shapely.geometry.GeometryCollection]`: Projected Shapely object
        
        Raises:
            `TypeError`: If type of Shapely object isn't one of: `Point`, `LineString`, `LinearRing`, `Polygon`, `MultiPoint`, `MultiLineString`, `MultiPolygon`, `GeometryCollection`
        """
        shapely_type = type(shapely_object)
        if shapely_type == shapely.geometry.Point: return shapely.geometry.Point(*self.project_point(shapely_object.x, shapely_object.y))
        elif shapely_type == shapely.geometry.LineString: return shapely.geometry.LineString(self.project_line(shapely_object.coords, interpolation))
        elif shapely_type == shapely.geometry.LinearRing: return shapely.geometry.LinearRing(self.project_polygon(shapely_object.coords, interpolation, True))
        elif shapely_type == shapely.geometry.Polygon: return shapely.geometry.Polygon(self.project_polygon(shapely_object.exterior.coords, interpolation, True), holes = [self.project_polygon(ring.coords, interpolation, True) for ring in shapely_object.interiors])
        elif shapely_type == shapely.geometry.MultiPoint: return shapely.geometry.MultiPoint(self.project_points([(point.x, point.y) for point in shapely_object]))
        elif shapely_type == shapely.geometry.MultiLineString: return shapely.geometry.MultiLineString([self.project_line(line.coords, interpolation) for line in shapely_object])
        elif shapely_type in [shapely.geometry.MultiPolygon, shapely.geometry.GeometryCollection]: return shapely_type([self.project_shapely_object(internal_shapely_object, interpolation) for internal_shapely_object in shapely_object])
        else: raise TypeError("Type of Shapely object must be one of [Point, LineString, LinearRing, Polygon, MultiPoint, MultiLineString, MultiPolygon, GeometryCollection]")
    
    def project_geojson_object(
        self, 
        geojson_object: dict, 
        interpolation: Optional[int] = None
    ) -> dict:
        """
        Projects a GeoJSON object (`Point`, `MultiPoint`, `LineString`, `MultiLineString`, `Polygon`, `MultiPolygon`, `GeometryCollection`) 
        from the start CRS to the destination CRS

        Args:
            `geojson_object` (`dict`): GeoJSON object
            `interpolation` (`int`, optional): Number of points projected per line (ignored if type is `Point`)

        Returns:
            `dict`: Projected GeoJSON object

        Raises:
            `TypeError`: If type of GeoJSON object isn't one of: `Point`, `MultiPoint`, `LineString`, `MultiLineString`, `Polygon`, `MultiPolygon`, `GeometryCollection`
        """
        new_geojson_object = {k: copy.deepcopy(v) for k, v in geojson_object.items() if k not in ['coordinates', 'geometries']} # no need to deep copy the coordinates
        geojson_type = geojson_object['type']
        if geojson_type == 'Point': new_geojson_object['coordinates'] = list(self.project_point(*geojson_object['coordinates']))
        elif geojson_type in ['MultiPoint', 'LineString']: new_geojson_object['coordinates'] = list(map(list, self.project_polygon(geojson_object['coordinates'], interpolation, True)))
        elif geojson_type in ['MultiLineString', 'Polygon']: new_geojson_object['coordinates'] = [list(map(list, self.project_polygon(shape, interpolation, True))) for shape in geojson_object['coordinates']]
        elif geojson_type == 'MultiPolygon': new_geojson_object['coordinates'] = [[list(map(list, self.project_polygon(ring, interpolation, True))) for ring in polygon] for polygon in geojson_object['coordinates']]
        elif geojson_type == 'GeometryCollection': new_geojson_object['geometries'] = [self.project_geojson_object(internal_geojson_object, interpolation) for internal_geojson_object in geojson_object['geometries']]
        else: raise TypeError("Type of GeoJSON object must be one of [Point, MultiPoint, LineString, MultiLineString, Polygon, MultiPolygon, GeometryCollection]")
        return new_geojson_object

    def project_tuple_transform(
        self, 
        transform: Tuple[float, float, float, float, float ,float], 
        points_from: Iterable[Union[Tuple[float, float], List[float]]]
    ) -> Tuple[float, float, float, float, float, float]:
        """
        Computes the affine transformation that best maps points in `points_from` to coordinates in the destination CRS
        using a least squares approach

        This function first projects points in `points_to` to the start CRS using `transform` and then to the destination CRS using `transformer`
        and finally uses `approximate_transform` to find the best fitting transform

        Args:
            `transform` (`Tuple[float, float, float, float, float ,float]`): Coefficients (a, b, c, d, e, f) of the affine geospatial transform that is being projected
            `points_from` (`Iterable[Union[Tuple[float, float], List[float]]]`): Points of the grid for which the projected transform will best fit
        
        Returns:
            `Tuple[float, float, float, float, float ,float]`: Projected transform
        """
        a, b, c, d, e, f = transform
        points_to = self.project_points([(a * x + b * y + c, d * x + e * y + f) for x, y in points_from])
        return approximate_transform(points_from, points_to)
    
    def project_tuple_transform_grid(
        self, 
        transform: Tuple[float, float, float, float, float ,float], 
        x_range: int,
        y_range: int, 
        b: int = 3
    ) -> Tuple[float, float, float, float, float ,float]:
        """
        Computes the affine transformation that best maps points on the grid of size `x_range` * `y_range` to coordinates in the destination CRS
        using a least squares approach

        This function first chooses a point for every `b` * `b` square of the grid using `generate_points`, 
        and then projects those points to the start CRS using `transform` and then to the destination CRS using `transformer`
        and finally uses `approximate_transform` to find the best fitting transform

        Args:
            `transform` (`Tuple[float, float, float, float, float ,float]`): Coefficients (a, b, c, d, e, f) of the affine geospatial transform that is being projected
            `x_range` (`int`): Possible x values on the grid (0-indexed)
            `y_range` (`int`): Possible y values on the grid (0-indexed)
            `b` (`int`, optional): Block size used to choose points
        
        Returns:
            `Tuple[float, float, float, float, float ,float]`: Projected transform
        """
        return self.project_tuple_transform(transform, generate_points(x_range, y_range, b))
    
    def project_affine_transform(
        self, 
        transform: Affine, 
        points_from: Iterable[Union[Tuple[float, float], List[float]]]
    ) -> Affine:
        """
        Computes the affine transformation that best maps points in `points_from` to coordinates in the destination CRS
        using a least squares approach

        This function first projects points in `points_from` to the start CRS using `transform` and then to the destination CRS using `transformer`
        and finally uses `approximate_transform` to find the best fitting transform

        Args:
            `transform` (`Affine`): Affine geospatial transform that is being projected
            `points_from` (`Iterable[Union[Tuple[float, float], List[float]]]`): Points of the grid for which the projected transform will best fit
        
        Returns:
            `Affine`: Projected transform
        """
        points_to = self.project_points([transform * (x, y) for x, y in points_from])
        return Affine(*approximate_transform(points_from, points_to))
    
    def project_affine_transform_grid(
        self, 
        transform: Affine, 
        x_range: int, 
        y_range: int,
        b: int = 3
    ) -> Affine:
        """
        Computes the affine transformation that best maps points on the grid of size `x_range` * `y_range` to coordinates in the destination CRS
        using a least squares approach

        This function first chooses a point for every `b` * `b` square of the grid using `generate_points`, 
        and then projects those points to the start CRS using `transform` and then to the destination CRS using `transformer`
        and finally uses `approximate_transform` to find the best fitting transform

        Args:
            `transform` (`Affine`): Affine geospatial transform that is being projected
            `x_range` (`int`): Possible x values on the grid (0-indexed)
            `y_range` (`int`): Possible y values on the grid (0-indexed)
            `b` (`int`, optional): Block size used to choose points
        
        Returns:
            `Affine`: Projected transform
        """
        return self.project_affine_transform(transform, generate_points(x_range, y_range, b))
