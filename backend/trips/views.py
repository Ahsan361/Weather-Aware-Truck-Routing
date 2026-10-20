from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .serializers import AnalyzeRequestSerializer
from .services.analysis import TripRequest, analyze_trip
from .services.geocoding import GeocodingError, GeocodingNotConfigured, search_places
from .services.routing import RoutingError
from .services.timezones import timezone_name_at
from .services.weather import OutsideForecast, RateLimited, WeatherError


@api_view(["GET"])
def health(request):
    return Response({"status": "ok"})


@api_view(["POST"])
def analyze(request):
    serializer = AnalyzeRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    origin = (data["origin"]["lon"], data["origin"]["lat"])
    destination = (data["destination"]["lon"], data["destination"]["lat"])
    trip = TripRequest(origin, destination, data["departure"], data["load_lb"], data["interval_miles"])

    try:
        result = analyze_trip(trip)
    except RoutingError as exc:
        return Response({"detail": f"Couldn't plan routes: {exc}"}, status=status.HTTP_502_BAD_GATEWAY)
    except OutsideForecast as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except RateLimited as exc:
        return Response(
            {"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE, headers={"Retry-After": "60"}
        )
    except WeatherError as exc:
        return Response({"detail": f"Couldn't get the forecast: {exc}"}, status=status.HTTP_502_BAD_GATEWAY)

    result["origin"] = {**data["origin"], "timezone": timezone_name_at(origin)}
    result["destination"] = dict(data["destination"])
    return Response(result)


@api_view(["GET"])
def geocode(request):
    try:
        places = search_places(request.query_params.get("q", ""))
    except GeocodingNotConfigured as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except GeocodingError as exc:
        return Response({"detail": f"Address search failed: {exc}"}, status=status.HTTP_502_BAD_GATEWAY)

    return Response({"results": [{"label": p.label, "lat": p.lat, "lon": p.lon} for p in places]})
