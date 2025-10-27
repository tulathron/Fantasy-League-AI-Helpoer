"""Async client for Sleeper fantasy football data."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional

import httpx

from .base import robust_get


BASE_URL = "https://api.sleeper.app/v1"


@dataclass(slots=True)
class SleeperPlayer:
    player_id: str
    name: str
    position: Optional[str]
    team: Optional[str]
    injury_status: Optional[str]
    injury_notes: Optional[str]
    fantasy_positions: List[str]
    espn_id: Optional[str]


class SleeperClient:
    """Wrapper around the Sleeper HTTP API."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client
        self._players_cache: Optional[Mapping[str, dict[str, Any]]] = None

    async def get_league_rosters(self, league_id: str) -> list[dict[str, Any]]:
        response = await robust_get(self._client, f"{BASE_URL}/league/{league_id}/rosters")
        return response.json()

    async def get_league_users(self, league_id: str) -> list[dict[str, Any]]:
        response = await robust_get(self._client, f"{BASE_URL}/league/{league_id}/users")
        return response.json()

    async def get_matchups(self, league_id: str, week: int) -> list[dict[str, Any]]:
        response = await robust_get(
            self._client,
            f"{BASE_URL}/league/{league_id}/matchups/{week}",
        )
        return response.json()

    async def get_player_details(self, player_ids: Iterable[str]) -> dict[str, SleeperPlayer]:
        player_map = await self._get_all_players()
        result: dict[str, SleeperPlayer] = {}
        for player_id in player_ids:
            raw = player_map.get(player_id)
            if raw:
                result[player_id] = SleeperPlayer(
                    player_id=player_id,
                    name=raw.get("full_name") or raw.get("first_name"),
                    position=raw.get("position"),
                    team=raw.get("team"),
                    injury_status=raw.get("injury_status"),
                    injury_notes=raw.get("injury_notes"),
                    fantasy_positions=list(raw.get("fantasy_positions") or []),
                    espn_id=str(raw["espn_id"]) if raw.get("espn_id") else None,
                )
        return result

    async def _get_all_players(self) -> Mapping[str, dict[str, Any]]:
        if self._players_cache is None:
            response = await robust_get(self._client, f"{BASE_URL}/players/nfl")
            self._players_cache = response.json()
        return self._players_cache


__all__ = ["SleeperClient", "SleeperPlayer"]
