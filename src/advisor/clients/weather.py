"""OpenWeatherMap client."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import httpx

from .base import robust_get


API_URL = "https://api.openweathermap.org/data/2.5/forecast"


@dataclass(slots=True)
class WeatherForecast:
    summary: str
    temperature_f: float
    wind_mph: float
    precipitation_probability: float
    kickoff_time: datetime


class WeatherClient:
    def __init__(self, client: httpx.AsyncClient, *, api_key: str) -> None:
        self._client = client
        self._api_key = api_key

    async def forecast_for_location(
        self,
        *,
        latitude: float,
        longitude: float,
        kickoff_time: datetime,
    ) -> Optional[WeatherForecast]:
        params = {
            "lat": latitude,
            "lon": longitude,
            "appid": self._api_key,
            "units": "imperial",
        }
        response = await robust_get(self._client, API_URL, params=params)
        payload = response.json()
        items = payload.get("list", [])
        if not items:
            return None

        kickoff = kickoff_time
        if kickoff.tzinfo is None:
            kickoff = kickoff.replace(tzinfo=timezone.utc)
        else:
            kickoff = kickoff.astimezone(timezone.utc)
        target_timestamp = kickoff.timestamp()
        closest = min(
            items,
            key=lambda item: abs(item.get("dt", 0) - target_timestamp),
        )
        weather = closest.get("weather", [{}])[0]
        main = closest.get("main", {})
        wind = closest.get("wind", {})
        pop = closest.get("pop", 0.0)

        return WeatherForecast(
            summary=weather.get("description", ""),
            temperature_f=float(main.get("temp", 0.0)),
            wind_mph=float(wind.get("speed", 0.0)),
            precipitation_probability=float(pop) * 100,
            kickoff_time=kickoff_time,
        )


__all__ = ["WeatherClient", "WeatherForecast"]
