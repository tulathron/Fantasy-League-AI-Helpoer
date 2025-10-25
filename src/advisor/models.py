"""Data models for aggregating fantasy information."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .clients.espn import PlayerPerformance, TeamGame
from .clients.fantasypros import FantasyProsProjection
from .clients.sleeper import SleeperPlayer
from .clients.weather import WeatherForecast


@dataclass(slots=True)
class PlayerContext:
    sleeper: SleeperPlayer
    matchup: Optional[str]
    expected_role: Optional[str]
    team_game: Optional[TeamGame]
    weather: Optional[WeatherForecast]
    recent_performance: list[PlayerPerformance] = field(default_factory=list)
    fantasypros_weekly: Optional[FantasyProsProjection] = None
    fantasypros_ros: Optional[FantasyProsProjection] = None

    def injury_summary(self) -> str:
        if not self.sleeper.injury_status:
            return "No reported injuries."
        details = self.sleeper.injury_status.upper()
        if self.sleeper.injury_notes:
            details = f"{details} - {self.sleeper.injury_notes}"
        return details

    def availability_flag(self) -> str:
        status = (self.sleeper.injury_status or "").lower()
        if status in {"ir", "out", "doubtful"}:
            return "high-risk availability"
        if status in {"questionable", "suspension"}:
            return "monitor closely"
        return "cleared"

    def weather_summary(self) -> str:
        if not self.weather:
            return "Indoor or weather data unavailable."
        w = self.weather
        return (
            f"{w.summary} at {w.temperature_f:.0f}F, wind {w.wind_mph:.0f} mph, "
            f"precipitation chance {w.precipitation_probability:.0f}%"
        )

    def performance_summary(self) -> str:
        if not self.recent_performance:
            return "No recent performance data."
        parts = []
        for perf in self.recent_performance:
            pts = f"{perf.fantasy_points:.1f} pts" if perf.fantasy_points is not None else "N/A"
            snap = f"{perf.snap_percentage:.0f}% snaps" if perf.snap_percentage is not None else "snap % N/A"
            parts.append(f"{perf.game_date.date()}: {pts}, {snap} vs {perf.opponent}")
        return " | ".join(parts)

    def fantasypros_summary(self) -> str:
        pieces: list[str] = []
        if self.fantasypros_weekly:
            fp = self.fantasypros_weekly
            pieces.append(
                f"Week projection {fp.projection:.1f} (ECR {fp.expert_consensus_rank:.0f}) vs {fp.opponent}"
                if fp.projection is not None and fp.expert_consensus_rank is not None
                else f"Week projection vs {fp.opponent or 'TBD'}"
            )
        if self.fantasypros_ros and not self.fantasypros_weekly:
            fp = self.fantasypros_ros
            pieces.append(
                f"ROS projection {fp.projection:.1f} (ECR {fp.expert_consensus_rank:.0f})"
                if fp.projection is not None and fp.expert_consensus_rank is not None
                else "ROS ranking available"
            )
        return " | ".join(pieces) if pieces else "No FantasyPros data."


@dataclass(slots=True)
class TeamContext:
    roster_id: int
    owner: str
    week: int
    players: dict[str, PlayerContext]

    def summary(self) -> str:
        lines = [f"Lineup recommendations for {self.owner} (week {self.week}):"]
        for player_ctx in self.players.values():
            lines.append(
                " - "
                + f"{player_ctx.sleeper.name} ({player_ctx.sleeper.position}) vs {player_ctx.matchup or 'TBD'}"
            )
        return "\n".join(lines)


__all__ = ["PlayerContext", "TeamContext"]
