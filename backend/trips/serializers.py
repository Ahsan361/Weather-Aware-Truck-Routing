from datetime import datetime, timedelta, timezone

from rest_framework import serializers

from .services.geo import haversine_miles
from .services.timezones import timezone_at

MAX_LOAD_LB = 100_000
INTERVAL_CHOICES = [10, 25, 50]
MAX_DAYS_AHEAD = 14


class PlaceSerializer(serializers.Serializer):
    lat = serializers.FloatField(min_value=-90, max_value=90)
    lon = serializers.FloatField(min_value=-180, max_value=180)
    label = serializers.CharField(required=False, allow_blank=True, max_length=200)

    @property
    def point(self):
        return self.validated_data["lon"], self.validated_data["lat"]


class AnalyzeRequestSerializer(serializers.Serializer):
    origin = PlaceSerializer()
    destination = PlaceSerializer()
    departure = serializers.CharField(
        help_text="ISO date-time. Without an offset it is read as local time at the origin."
    )
    load_lb = serializers.FloatField(min_value=0, max_value=MAX_LOAD_LB)
    interval_miles = serializers.ChoiceField(choices=INTERVAL_CHOICES, default=25)

    def validate(self, attrs):
        origin = (attrs["origin"]["lon"], attrs["origin"]["lat"])
        destination = (attrs["destination"]["lon"], attrs["destination"]["lat"])
        if haversine_miles(origin, destination) < 1:
            raise serializers.ValidationError({"destination": "Pick a destination at least a mile from the origin."})

        attrs["departure"] = self._parse_departure(attrs["departure"], origin)
        return attrs

    def _parse_departure(self, raw: str, origin) -> datetime:
        try:
            departure = datetime.fromisoformat(raw)
        except ValueError:
            raise serializers.ValidationError({"departure": "Use a date and time like 2026-11-03T06:00."}) from None

        if departure.tzinfo is None:
            departure = departure.replace(tzinfo=timezone_at(origin))
        departure = departure.astimezone(timezone.utc)

        now = datetime.now(timezone.utc)
        if departure < now - timedelta(hours=1):
            raise serializers.ValidationError({"departure": "Departure can't be in the past."})
        if departure > now + timedelta(days=MAX_DAYS_AHEAD):
            raise serializers.ValidationError(
                {"departure": f"Forecasts only reach about {MAX_DAYS_AHEAD} days ahead."}
            )
        return departure
