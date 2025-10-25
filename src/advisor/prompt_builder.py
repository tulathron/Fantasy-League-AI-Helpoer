"""Prompt construction for OpenAI."""
from __future__ import annotations

from typing import Iterable

from .models import PlayerContext, TeamContext


def build_player_section(player: PlayerContext) -> str:
    lines = [
        f"Player: {player.sleeper.name} ({player.sleeper.position})",
        f"Team: {player.sleeper.team or 'FA'} vs {player.matchup or 'TBD'}",
        f"Injury: {player.injury_summary()} ({player.availability_flag()})",
        f"Role: {player.expected_role or 'Not specified'}",
        f"Weather: {player.weather_summary()}",
        f"Recent performance: {player.performance_summary()}",
        f"FantasyPros: {player.fantasypros_summary()}",
    ]
    return "\n".join(lines)


def build_prompt(team: TeamContext) -> str:
    sections = [
        "You are an elite fantasy football analyst. Provide a concise but thorough recommendation",
        "for the starting lineup this week. Prioritize player availability, expected workload,",
        "weather risk, opponent strength, and recent performance trends. Highlight any players",
        "returning from injury reserve (IR) or with limited practice participation. Recommend",
        "specific start/sit decisions and justify them with the data provided.",
        "\n",
        team.summary(),
        "\nPlayer details:",
    ]

    for player in team.players.values():
        sections.append("\n" + build_player_section(player))

    sections.append(
        "\nRespond with actionable advice, including a ranked list of suggested starters,"
        "bench considerations, and matchup/weather caveats."
    )
    return "\n".join(sections)


__all__ = ["build_prompt", "build_player_section"]
