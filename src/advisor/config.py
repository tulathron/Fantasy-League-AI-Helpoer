"""Configuration helpers for the Fantasy League AI Helper application."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional
import json


@dataclass(slots=True)
class Credentials:
    """Represents API credentials used by the advisor."""

    openai_api_key: str
    openweather_api_key: str
    fantasypros_api_key: Optional[str] = None
    espn_s2: Optional[str] = None
    swid: Optional[str] = None


class CredentialLoaderError(RuntimeError):
    """Raised when credentials cannot be loaded."""


def _load_raw_credentials(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise CredentialLoaderError(
            f"Credential file '{path}' does not exist. Create it from credentials.example.json"
        )
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise CredentialLoaderError(f"Invalid JSON in credential file: {path}") from exc


def load_credentials(path: str | Path) -> Credentials:
    """Load credentials from ``credentials.json`` or another file.

    Parameters
    ----------
    path:
        Path to the credential file.

    Returns
    -------
    Credentials
        Parsed credential values.
    """

    raw = _load_raw_credentials(Path(path))

    def _require(name: str) -> str:
        value = raw.get(name)
        if not isinstance(value, str) or not value.strip():
            raise CredentialLoaderError(f"Credential '{name}' is required but missing or empty.")
        return value

    openai_key = _require("openai_api_key")
    openweather_key = _require("openweather_api_key")
    fantasypros_key = raw.get("fantasypros_api_key")
    espn_s2 = raw.get("espn_s2")
    swid = raw.get("swid")

    return Credentials(
        openai_api_key=openai_key,
        openweather_api_key=openweather_key,
        fantasypros_api_key=fantasypros_key,
        espn_s2=espn_s2,
        swid=swid,
    )


__all__ = ["Credentials", "CredentialLoaderError", "load_credentials"]
