import math

EARTH_RADIUS_MILES = 3958.8
METERS_PER_MILE = 1609.344

Point = tuple[float, float]  # (longitude, latitude), same order as GeoJSON and OSRM


def haversine_miles(a: Point, b: Point) -> float:
    lon1, lat1, lon2, lat2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_MILES * math.asin(math.sqrt(h))


def sideways_point(origin: Point, destination: Point, fraction: float, offset_miles: float) -> Point:
    lon = origin[0] + (destination[0] - origin[0]) * fraction
    lat = origin[1] + (destination[1] - origin[1]) * fraction

    miles_per_deg_lat = 69.0
    miles_per_deg_lon = 69.17 * math.cos(math.radians(lat))
    dx = (destination[0] - origin[0]) * miles_per_deg_lon
    dy = (destination[1] - origin[1]) * miles_per_deg_lat
    length = math.hypot(dx, dy)
    if length == 0:
        return lon, lat

    # unit vector turned 90 degrees to the left
    left_x, left_y = -dy / length, dx / length
    return (
        lon + left_x * offset_miles / miles_per_deg_lon,
        lat + left_y * offset_miles / miles_per_deg_lat,
    )


def simplify(points: list[Point], tolerance_miles: float) -> list[Point]:
    if len(points) < 3:
        return list(points)

    # work in flat miles around the middle of the line, this is good enough at road scale 
    mid_lat = sum(lat for _, lat in points) / len(points)
    kx, ky = 69.17 * math.cos(math.radians(mid_lat)), 69.0
    xy = [(lon * kx, lat * ky) for lon, lat in points]

    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        first, last = stack.pop()
        ax, ay = xy[first]
        bx, by = xy[last]
        dx, dy = bx - ax, by - ay
        length_sq = dx * dx + dy * dy

        farthest, farthest_dist = -1, tolerance_miles
        for i in range(first + 1, last):
            px, py = xy[i]
            if length_sq == 0:
                dist = math.hypot(px - ax, py - ay)
            else:
                t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length_sq))
                dist = math.hypot(px - (ax + t * dx), py - (ay + t * dy))
            if dist > farthest_dist:
                farthest, farthest_dist = i, dist

        if farthest != -1:
            keep[farthest] = True
            stack.append((first, farthest))
            stack.append((farthest, last))

    return [p for p, kept in zip(points, keep) if kept]
