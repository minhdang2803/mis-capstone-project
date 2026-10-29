import pytest

from app.core.geometry import (
    distance_to_polyline,
    from_local_xy,
    haversine_distance,
    to_local_xy,
)

LAT, LON = 10.80, 106.70


def offset(dx_m, dy_m):
    return list(from_local_xy(dx_m, dy_m, LAT, LON))


def test_local_projection_roundtrip():
    x, y = to_local_xy(10.805, 106.708, LAT, LON)
    assert from_local_xy(x, y, LAT, LON) == pytest.approx((10.805, 106.708), abs=1e-9)


def test_segment_distance_catches_crossing_between_vertices():
    # Two vertices 1 km apart on either side of the hazard: vertex-only checks see >= 500 m.
    route = [offset(-500, 20), offset(500, 20)]
    hit = distance_to_polyline(route, LAT, LON)
    vertex_only = min(haversine_distance(p[0], p[1], LAT, LON) for p in route)
    assert vertex_only > 450
    assert hit["distance_m"] == pytest.approx(20, abs=1)
    assert hit["segment_index"] == 0
    assert hit["closest_point"] == pytest.approx(offset(0, 20), abs=1e-6)


def test_distance_to_endpoint_when_projection_falls_outside_segment():
    route = [offset(100, 0), offset(300, 0)]
    assert distance_to_polyline(route, LAT, LON)["distance_m"] == pytest.approx(100, abs=1)


def test_picks_the_closest_of_several_segments():
    route = [offset(-400, 300), offset(-100, 300), offset(-100, 80), offset(300, 80)]
    hit = distance_to_polyline(route, LAT, LON)
    assert hit["segment_index"] == 2
    assert hit["distance_m"] == pytest.approx(80, abs=1)


def test_degenerate_polylines():
    assert distance_to_polyline([], LAT, LON)["distance_m"] == float("inf")
    one = distance_to_polyline([offset(30, 40)], LAT, LON)
    assert one["distance_m"] == pytest.approx(50, abs=1)
