from crswitch import Projector
from crswitch.util import generate_points
from rasterio import Affine
from math import sqrt

def dist(p1, p2):
    return sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)

def test_project_transform():
    size = 2048
    transform = Affine(1.953125, 0.0, 3953800.0, 0.0, -1.953125, 4011000.0)

    projector = Projector(3857, 4326)
    points = generate_points(size, size)

    new_transform = projector.project_transform_custom(transform, points)

    real_final_coordinates = projector.project_points([transform * point for point in points])
    approximate_final_coordinates = [new_transform * point for point in points]

    print(max(sqrt(dist(real_final_coordinates[i], approximate_final_coordinates[i])) for i in range(len(points))))

test_project_transform()