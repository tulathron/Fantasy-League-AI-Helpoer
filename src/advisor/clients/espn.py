"""ESPN data client for advanced context."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, Optional

import httpx

from .base import robust_get


BASE_URL = "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl"
KONA_PLAYER_URL = "https://site.api.espn.com/apis/fantasy/v2/games/ffl/seasons/{season}/segments/0/leaguedefaults/1"


@dataclass(slots=True)
class PlayerPerformance:
    player_id: str
    season: int
    game_date: datetime
    opponent: Optional[str]
    team: Optional[str]
    fantasy_points: Optional[float]
    snap_percentage: Optional[float]


@dataclass(slots=True)
class TeamGame:
    opponent_abbrev: Optional[str]
    home: bool
    stadium: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    game_date: Optional[datetime]


class ESPNClient:
    def __init__(self, client: httpx.AsyncClient, *, espn_s2: Optional[str] = None, swid: Optional[str] = None) -> None:
        self._client = client
        self._cookies = {}
        if espn_s2:
            self._cookies["espn_s2"] = espn_s2
        if swid:
            self._cookies["SWID"] = swid

    async def get_player_performance(self, espn_player_id: str, *, season: int, limit: int = 5) -> list[PlayerPerformance]:
        """Fetch recent player performance stats."""

        player_url = f"{BASE_URL}/athletes/{espn_player_id}/events"
        response = await robust_get(self._client, player_url)
        events: list[dict[str, Any]] = response.json().get("items", [])
        performances: list[PlayerPerformance] = []

        for event in events[:limit]:
            try:
                summary = await self._fetch_event_summary(event.get("$ref"))
            except httpx.HTTPError:
                continue

            competitions = summary.get("competitions", [])
            if not competitions:
                continue
            competition = competitions[0]
            status = competition.get("status", {}).get("type", {})
            date_str = status.get("detail") or competition.get("date")
            game_date = None
            if date_str:
                try:
                    game_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                except ValueError:
                    pass

            # determine opponent info
            teams = competition.get("competitors", [])
            opponent_abbrev = None
            player_team_abbrev = None
            for team in teams:
                team_info = team.get("team", {})
                abbrev = team_info.get("abbreviation")
                if team.get("id") == espn_player_id:
                    player_team_abbrev = abbrev
                else:
                    opponent_abbrev = abbrev

            stats = competition.get("statistics", [])
            fantasy_points = None
            snap_pct = None
            for stat in stats:
                if stat.get("name") == "fantasyPoints":
                    try:
                        fantasy_points = float(stat.get("value"))
                    except (TypeError, ValueError):
                        fantasy_points = None
                if stat.get("name") == "snapShare":
                    try:
                        snap_pct = float(stat.get("value"))
                    except (TypeError, ValueError):
                        snap_pct = None

            performances.append(
                PlayerPerformance(
                    player_id=espn_player_id,
                    season=season,
                    game_date=game_date or datetime.now(),
                    opponent=opponent_abbrev,
                    team=player_team_abbrev,
                    fantasy_points=fantasy_points,
                    snap_percentage=snap_pct,
                )
            )

        return performances

    async def get_team_game(self, team_abbrev: str, *, season: int, week: int) -> Optional[TeamGame]:
        """Return the schedule info for a team in the given week."""

        schedule_url = f"{BASE_URL}/teams/{team_abbrev.lower()}/schedule"
        response = await robust_get(self._client, schedule_url)
        items: list[dict[str, Any]] = response.json().get("items", [])
        for item in items:
            ref = item.get("$ref")
            if not ref:
                continue
            schedule = await self._fetch_schedule_item(ref)
            game_week = schedule.get("week", {}).get("number")
            if game_week != week:
                continue
            competitions = schedule.get("competitions", [])
            if not competitions:
                continue
            comp = competitions[0]
            venue = comp.get("venue", {})
            coords = venue.get("address", {})
            home = comp.get("competitors", [{}])[0].get("homeAway") == "home"
            opponent_abbrev = None
            for competitor in comp.get("competitors", []):
                if competitor.get("team", {}).get("abbreviation", "").lower() != team_abbrev.lower():
                    opponent_abbrev = competitor.get("team", {}).get("abbreviation")
                    break
            date_str = comp.get("date")
            game_date = None
            if date_str:
                try:
                    game_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                except ValueError:
                    pass

            return TeamGame(
                opponent_abbrev=opponent_abbrev,
                home=home,
                stadium=venue.get("fullName") or venue.get("address", {}).get("city"),
                latitude=_safe_float(coords.get("latitude")),
                longitude=_safe_float(coords.get("longitude")),
                game_date=game_date,
            )
        return None

    async def _fetch_event_summary(self, url: Optional[str]) -> dict[str, Any]:
        if not url:
            return {}
        response = await robust_get(self._client, url, headers={"Accept": "application/json"})
        return response.json()

    async def _fetch_schedule_item(self, url: str) -> dict[str, Any]:
        response = await robust_get(self._client, url, headers={"Accept": "application/json"})
        return response.json()


def _safe_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


__all__ = ["ESPNClient", "PlayerPerformance", "TeamGame"]
