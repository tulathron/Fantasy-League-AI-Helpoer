"""Command line interface for the Fantasy League AI Helper."""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from advisor.advisor_service import FantasyAdvisor
from advisor.config import load_credentials


async def _run_async(args: argparse.Namespace) -> None:
    credentials = load_credentials(args.credentials)
    advisor = FantasyAdvisor(credentials)
    advice = await advisor.advise_lineup(
        league_id=args.league_id,
        week=args.week,
        roster_id=args.roster_id,
    )
    print(advice)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fantasy football lineup advisor")
    parser.add_argument("league_id", help="Sleeper league ID")
    parser.add_argument("week", type=int, help="Week number to evaluate")
    parser.add_argument(
        "--credentials",
        default=Path("credentials.json"),
        type=Path,
        help="Path to credentials JSON file",
    )
    parser.add_argument(
        "--roster-id",
        type=int,
        help="Specific roster ID (defaults to first roster)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    asyncio.run(_run_async(args))


if __name__ == "__main__":
    main()
