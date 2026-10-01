"""Public modules using unauthenticated Exposure Events endpoints."""

from .public_client import PublicExposureClient
from .team_checker import check_team_pattern, TeamMatch
from .game_extractor import extract_team_games, GameInfo
from .event_finder import find_events_ma_nh, Event
from .calendar_export import (
    games_to_ics, 
    save_ics_file, 
    create_email_itinerary,
    save_email_itinerary,
    send_email_via_resend,
)
from .main import run_with_known_events, run_auto_discovery, generate_email_itinerary

__all__ = [
    "PublicExposureClient",
    "check_team_pattern",
    "TeamMatch",
    "extract_team_games",
    "GameInfo",
    "find_events_ma_nh",
    "Event",
    "games_to_ics",
    "save_ics_file",
    "create_email_itinerary",
    "save_email_itinerary",
    "send_email_via_resend",
    "run_with_known_events",
    "run_auto_discovery",
    "generate_email_itinerary",
]

__version__ = "1.0.0"