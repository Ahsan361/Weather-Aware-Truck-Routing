from trips.services.geo import haversine_miles
from trips.services.routing import Route


def make_route(points, mph=60.0):
    miles = [haversine_miles(a, b) for a, b in zip(points, points[1:])]
    seconds = [mi / mph * 3600 for mi in miles]
    return Route(list(points), miles, seconds)


def east_west_line(lat, lon_from=0.0, lon_to=2.0, steps=100):
    step = (lon_to - lon_from) / steps
    return [(lon_from + i * step, lat) for i in range(steps + 1)]


def simple_route(segment_miles, segment_seconds):
    coords = [(float(i), 0.0) for i in range(len(segment_miles) + 1)]
    return Route(coords, list(segment_miles), list(segment_seconds))
