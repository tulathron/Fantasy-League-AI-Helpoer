"""Fantasy lineup advisor orchestration."""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Iterable, Optional

import httpx
from openai import OpenAI

from .clients.base import HttpClientFactory
from .clients.espn import ESPNClient
from .clients.fantasypros import FantasyProsClient
from .clients.sleeper import SleeperClient, SleeperPlayer
from .clients.weather import WeatherClient
from .config import Credentials
from .models import PlayerContext, TeamContext
from .prompt_builder import build_prompt


class FantasyAdvisor:
    def __init__(self, credentials: Credentials) -> None:
        self._credentials = credentials
        self._http_factory = HttpClientFactory()
        self._openai = OpenAI(api_key=credentials.openai_api_key)

    async def advise_lineup(
        self,
        *,
        league_id: str,
        week: int,
        roster_id: Optional[int] = None,
    ) -> str:
        """Produce lineup advice for a specific roster.

        Parameters
        ----------
        league_id: str
            Sleeper league identifier.
        week: int
            Week to evaluate.
        roster_id: Optional[int]
            Optional roster id; if omitted, the first roster is used.
        """

        async with self._http_factory.client() as http_client:
            sleeper = SleeperClient(http_client)
            espn = ESPNClient(
                http_client,
                espn_s2=self._credentials.espn_s2,
                swid=self._credentials.swid,
            )
            fantasypros = FantasyProsClient(http_client, api_key=self._credentials.fantasypros_api_key)
            weather = WeatherClient(http_client, api_key=self._credentials.openweather_api_key)

            rosters, users, matchups = await asyncio.gather(
                sleeper.get_league_rosters(league_id),
                sleeper.get_league_users(league_id),
                sleeper.get_matchups(league_id, week),
            )

            roster_map = {r["roster_id"]: r for r in rosters if r.get("roster_id") is not None}
            if not roster_map:
                raise ValueError(f"No rosters found for Sleeper league {league_id}.")

            owner_map: dict[int, str] = {}
            for roster in rosters:
                rid = roster.get("roster_id")
                if rid is None:
                    continue
                owner_map[rid] = self._lookup_owner_name(roster.get("owner_id"), users)

            target_roster_id = roster_id if roster_id is not None else next(iter(roster_map))
            target_roster = roster_map.get(target_roster_id)
            if target_roster is None:
                raise ValueError(
                    f"Sleeper roster id {target_roster_id} was not found in league {league_id}."
                )

            owner = owner_map.get(target_roster_id, "Unknown Manager")
            player_ids = [pid for pid in target_roster.get("players", []) if pid]
            player_details = await sleeper.get_player_details(player_ids)

            roster_matchups = _build_roster_matchups(matchups, owner_map)
            player_matchups = _map_player_matchups(matchups, roster_matchups)

            # Build contexts concurrently for efficiency
            players_context: dict[str, PlayerContext] = {}
            tasks = [
                self._build_player_context(
                    sleeper_player=player_details.get(pid),
                    espn_client=espn,
                    fantasypros_client=fantasypros,
                    weather_client=weather,
                    matchup_text=player_matchups.get(pid),
                    week=week,
                )
                for pid in player_ids
                if player_details.get(pid)
            ]

            results = await asyncio.gather(*tasks)
            for context in results:
                if context:
                    players_context[context.sleeper.player_id] = context

            team = TeamContext(
                roster_id=target_roster["roster_id"],
                owner=owner,
                week=week,
                players=players_context,
            )

        prompt = build_prompt(team)
        response = self._openai.responses.create(
            model="gpt-4.1-mini",
            input=[{"role": "user", "content": prompt}],
            temperature=0.4,
        )
        return response.output_text

    async def _build_player_context(
        self,
        *,
        sleeper_player: SleeperPlayer,
        espn_client: ESPNClient,
        fantasypros_client: FantasyProsClient,
        weather_client: WeatherClient,
        matchup_text: Optional[str],
        week: int,
    ) -> Optional[PlayerContext]:
        expected_role = _expected_role_from_status(sleeper_player)
        team_game = None
        weather = None

        if sleeper_player.team:
            try:
                team_game = await espn_client.get_team_game(
                    sleeper_player.team,
                    season=_current_season(),
                    week=week,
                )
            except httpx.HTTPError:
                team_game = None
            if team_game and team_game.latitude and team_game.longitude and team_game.game_date:
                try:
                    weather = await weather_client.forecast_for_location(
                        latitude=team_game.latitude,
                        longitude=team_game.longitude,
                        kickoff_time=team_game.game_date,
                    )
                except httpx.HTTPError:
                    weather = None

        recent_performance = []
        if sleeper_player.espn_id:
            try:
                recent_performance = await espn_client.get_player_performance(
                    sleeper_player.espn_id,
                    season=_current_season(),
                    limit=4,
                )
            except httpx.HTTPError:
                recent_performance = []

        fantasypros_weekly = None
        fantasypros_ros = None
        if sleeper_player.position:
            fp_weekly = fp_ros = []
            try:
                fp_weekly, fp_ros = await asyncio.gather(
                    fantasypros_client.get_weekly_projection(week, sleeper_player.position),
                    fantasypros_client.get_rest_of_season_rank(sleeper_player.position),
                )
            except httpx.HTTPError:
                fp_weekly, fp_ros = [], []
            fantasypros_weekly = _find_projection_for_player(fp_weekly, sleeper_player.name)
            fantasypros_ros = _find_projection_for_player(fp_ros, sleeper_player.name)

        return PlayerContext(
            sleeper=sleeper_player,
            matchup=matchup_text,
            expected_role=expected_role,
            team_game=team_game,
            weather=weather,
            recent_performance=recent_performance,
            fantasypros_weekly=fantasypros_weekly,
            fantasypros_ros=fantasypros_ros,
        )

    def _lookup_owner_name(self, owner_id: str, users: Iterable[dict]) -> str:
        for user in users:
            if user.get("user_id") == owner_id:
                return user.get("display_name") or user.get("username") or "Unknown Manager"
        return "Unknown Manager"


def _current_season() -> int:
    today = datetime.utcnow()
    return today.year if today.month >= 3 else today.year - 1


def _expected_role_from_status(player: SleeperPlayer) -> str:
    status = (player.injury_status or "").lower()
    if status == "ir":
        return "Returning from IR, expect snap count monitoring"
    if status in {"questionable", "doubtful"}:
        return "Limited practice, monitor final injury report"
    return "Projected starter"


def _find_projection_for_player(
    projections: Iterable, player_name: Optional[str]
):
    normalized = (player_name or "").lower()
    for projection in projections:
        if projection.name and projection.name.lower() == normalized:
            return projection
    return None


def _build_roster_matchups(matchups: Iterable[dict], owner_map: dict[int, str]) -> dict[int, dict[str, Optional[str]]]:
    by_matchup: dict[int, list[dict]] = {}
    for matchup in matchups:
        matchup_id = matchup.get("matchup_id")
        if matchup_id is None:
            continue
        by_matchup.setdefault(matchup_id, []).append(matchup)

    roster_matchups: dict[int, dict[str, Optional[str]]] = {}
    for matchup_id, roster_entries in by_matchup.items():
        for entry in roster_entries:
            roster_id = entry.get("roster_id")
            if roster_id is None:
                continue
            opponent_entry = next(
                (e for e in roster_entries if e.get("roster_id") != roster_id),
                None,
            )
            opponent_roster_id = opponent_entry.get("roster_id") if opponent_entry else None
            roster_matchups[roster_id] = {
                "matchup_id": matchup_id,
                "opponent_roster_id": opponent_roster_id,
                "opponent_owner": owner_map.get(opponent_roster_id) if opponent_roster_id else None,
            }
    return roster_matchups


def _map_player_matchups(matchups: Iterable[dict], roster_matchups: dict[int, dict[str, Optional[str]]]) -> dict[str, str]:
    player_lookup: dict[str, str] = {}
    for matchup in matchups:
        roster_id = matchup.get("roster_id")
        if roster_id is None:
            continue
        matchup_info = roster_matchups.get(roster_id) or {}
        opponent_owner = matchup_info.get("opponent_owner")
        matchup_id = matchup_info.get("matchup_id")
        opponent_label = opponent_owner or "Unknown opponent"
        description = f"vs {opponent_label} (matchup {matchup_id})" if matchup_id else f"vs {opponent_label}"
        for player_id in matchup.get("players") or []:
            player_lookup[player_id] = description
    return player_lookup


__all__ = ["FantasyAdvisor"]
