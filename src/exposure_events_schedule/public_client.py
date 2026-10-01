import re
import requests
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Event:
    id: int
    name: str
    slug: str
    start_date: str
    end_date: str
    city: str
    state: str
    venue: str
    organization: str
    url: str
    raw_data: Dict[str, Any]

    @property
    def event_url(self) -> str:
        return f"https://basketball.exposureevents.com/{self.id}/{self.slug}"

    @property
    def teams_url(self) -> str:
        return f"https://basketball.exposureevents.com/{self.id}/{self.slug}/teams"

    @property
    def schedule_url(self) -> str:
        return f"https://basketball.exposureevents.com/{self.id}/{self.slug}/schedule"

    @property
    def search_api_url(self) -> str:
        return f"https://basketball.exposureevents.com/{self.id}/{self.slug}/search?eventid={self.id}&eventname={self.slug}"


class PublicExposureClient:
    """Client for unauthenticated Exposure Events endpoints."""

    BASE_URL = "https://basketball.exposureevents.com"
    ICAL_URL = "https://ical.exposureevents.com"

    def __init__(self, timeout: int = 30):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/html, */*",
        })
        self.timeout = timeout

    def get_event_search_data(self, event_id: int, event_slug: str) -> Optional[Dict[str, Any]]:
        """Get teams, divisions, locations for an event via unauthenticated search endpoint."""
        url = f"{self.BASE_URL}/{event_id}/{event_slug}/search"
        params = {"eventid": event_id, "eventname": event_slug}
        try:
            resp = self.session.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"Error fetching search data for event {event_id}: {e}")
            return None

    def get_teams_html(self, event_id: int, event_slug: str) -> Optional[str]:
        """Get teams page HTML."""
        url = f"{self.BASE_URL}/{event_id}/{event_slug}/teams"
        try:
            resp = self.session.get(url, timeout=self.timeout)
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            print(f"Error fetching teams page for event {event_id}: {e}")
            return None

    def get_schedule_html(self, event_id: int, event_slug: str) -> Optional[str]:
        """Get schedule page HTML."""
        url = f"{self.BASE_URL}/{event_id}/{event_slug}/schedule"
        try:
            resp = self.session.get(url, timeout=self.timeout)
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            print(f"Error fetching schedule page for event {event_id}: {e}")
            return None

    def get_standings_html(self, event_id: int, event_slug: str) -> Optional[str]:
        """Get standings HTML."""
        url = f"{self.BASE_URL}/{event_id}/{event_slug}/documents/standings"
        params = {"type": "division"}
        try:
            resp = self.session.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            print(f"Error fetching standings for event {event_id}: {e}")
            return None

    def get_interactive_schedule(self, event_id: int, division_id: Optional[int] = None) -> Optional[str]:
        """Get interactive schedule HTML (loads games via JS)."""
        url = f"{self.BASE_URL}/interactive/schedule"
        params = {"eventid": event_id}
        if division_id:
            params["divisionid"] = division_id
        try:
            resp = self.session.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            print(f"Error fetching interactive schedule for event {event_id}: {e}")
            return None

    def get_game_ical(self, game_id: int, expired_timestamp: Optional[int] = None) -> Optional[str]:
        """Get individual game iCal."""
        if expired_timestamp is None:
            expired_timestamp = int(datetime.now().timestamp()) + 86400 * 365
        url = f"{self.ICAL_URL}/calendar-game.ics"
        params = {"expired": expired_timestamp, "gameid": game_id}
        try:
            resp = self.session.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            print(f"Error fetching iCal for game {game_id}: {e}")
            return None

    def parse_search_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse the search API response into structured data."""
        return {
            "teams": data.get("Teams", []),
            "divisions": data.get("Divisions", []),
            "locations": data.get("Locations", []),
            "players": data.get("Players", []),
            "team_url_template": data.get("TeamUrl", ""),
            "player_url_template": data.get("PlayerUrl", ""),
        }

    def find_team_by_pattern(self, teams: List[Dict[str, Any]], pattern: str) -> List[Dict[str, Any]]:
        """Find teams matching a wildcard pattern (supports * as wildcard)."""
        regex_pattern = pattern.replace("*", ".*")
        regex = re.compile(regex_pattern, re.IGNORECASE)
        matches = []
        for team in teams:
            name = team.get("Name", "")
            if regex.search(name):
                matches.append(team)
        return matches


def extract_event_id_from_url(url: str) -> Optional[int]:
    """Extract event ID from Exposure Events URL."""
    match = re.search(r"/(\d{5,8})/", url)
    if match:
        return int(match.group(1))
    return None