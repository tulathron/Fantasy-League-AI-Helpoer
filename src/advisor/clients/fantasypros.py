"""FantasyPros data client."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import httpx

from .base import robust_get


BASE_URL = "https://api.fantasypros.com/public/v2/json/nfl"


@dataclass(slots=True)
class FantasyProsProjection:
    player_id: str
    name: str
    position: Optional[str]
    team: Optional[str]
    opponent: Optional[str]
    projection: Optional[float]
    expert_consensus_rank: Optional[float]


class FantasyProsClient:
    def __init__(self, client: httpx.AsyncClient, *, api_key: Optional[str] = None) -> None:
        self._client = client
        self._api_key = api_key

    async def get_rest_of_season_rank(self, position: str) -> list[FantasyProsProjection]:
        """Return rest-of-season projections for a given position."""

        url = f"{BASE_URL}/players/ros"
        headers = {"x-api-key": self._api_key} if self._api_key else None
        response = await robust_get(self._client, url, params={"position": position}, headers=headers)
        payload = response.json()
        players = payload.get("players", [])
        projections: list[FantasyProsProjection] = []
        for player in players:
            projections.append(
                FantasyProsProjection(
                    player_id=str(player.get("player_id")),
                    name=player.get("player_name"),
                    position=player.get("position"),
                    team=player.get("team"),
                    opponent=player.get("opp"),
                    projection=_safe_float(player.get("proj_points")),
                    expert_consensus_rank=_safe_float(player.get("ecr")),
                )
            )
        return projections

    async def get_weekly_projection(self, week: int, position: str) -> list[FantasyProsProjection]:
        url = f"{BASE_URL}/players/projections"
        headers = {"x-api-key": self._api_key} if self._api_key else None
        response = await robust_get(
            self._client,
            url,
            params={"week": week, "position": position},
            headers=headers,
        )
        payload = response.json()
        players = payload.get("players", [])
        projections: list[FantasyProsProjection] = []
        for player in players:
            projections.append(
                FantasyProsProjection(
                    player_id=str(player.get("player_id")),
                    name=player.get("player_name"),
                    position=player.get("position"),
                    team=player.get("team"),
                    opponent=player.get("opp"),
                    projection=_safe_float(player.get("proj_points")),
                    expert_consensus_rank=_safe_float(player.get("ecr")),
                )
            )
        return projections


def _safe_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


__all__ = ["FantasyProsClient", "FantasyProsProjection"]
