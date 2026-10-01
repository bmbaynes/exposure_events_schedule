import re
import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from .public_client import PublicExposureClient


@dataclass
class GameInfo:
    game_id: int
    event_id: int
    event_name: str
    event_slug: str
    team_name: str
    opponent: str
    is_home: bool
    date: str
    time: str
    venue: str
    court: str
    division: str
    bracket: str
    round: int
    home_score: Optional[float] = None
    away_score: Optional[float] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)

    @property
    def datetime_str(self) -> str:
        return f"{self.date} {self.time}"

    @property
    def ical_url(self) -> str:
        return f"https://ical.exposureevents.com/calendar-game.ics?expired=1791072000&gameid={self.game_id}"

    @property
    def game_url(self) -> str:
        return f"https://basketball.exposureevents.com/{self.event_id}/{self.event_slug}/game?gameid={self.game_id}"


def _fetch_event_games(client: PublicExposureClient, event_id: int, event_slug: str, division_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Fetch games from the eventgames AJAX endpoint."""
    url = f"{client.BASE_URL}/{event_id}/{event_slug}/eventgames"
    data = {
        'divisionId': division_id if division_id else 0,
        'date': '',
        'ignoreResults': False,
    }
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'X-Requested-With': 'XMLHttpRequest',
    }
    try:
        resp = client.session.post(url, data=data, headers=headers, timeout=client.timeout)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"Error fetching event games: {e}")
        return []


def _parse_game_date(date_str: str) -> tuple:
    """Parse date string like 'Saturday, October 3, 2026' into date and time components."""
    # The date format from the API is like "Saturday, October 3, 2026"
    # Time is separate in the game object
    try:
        # Just return the date part for now
        dt = datetime.strptime(date_str, "%A, %B %d, %Y")
        return dt.strftime("%m/%d/%Y"), ""
    except ValueError:
        return date_str, ""


def extract_team_games(
    client: PublicExposureClient,
    event_id: int,
    event_slug: str,
    event_name: str,
    team_name: str,
    team_id: Optional[int] = None,
    division_id: Optional[int] = None,
) -> List[GameInfo]:
    """
    Extract games for a specific team from an event using the AJAX eventgames endpoint.
    
    This uses the same AJAX endpoint that the interactive schedule uses.
    """
    games = []
    
    # Fetch games from the AJAX endpoint
    days_data = _fetch_event_games(client, event_id, event_slug, division_id)
    
    if not days_data:
        return games
    
    # The response is a list of days, each with a list of games
    for day in days_data:
        day_name = day.get("Name", "")
        day_games = day.get("Games", [])
        
        for game in day_games:
            # Check if this game involves our team
            away_team = game.get("AwayTeamName", "")
            home_team = game.get("HomeTeamName", "")
            away_team_id = game.get("AwayDivisionTeamId")
            home_team_id = game.get("HomeDivisionTeamId")
            
            # Match by team ID (divisionteamid) only - exact match
            is_our_team = False
            is_home = False
            opponent = ""
            
            if team_id and (away_team_id == team_id or home_team_id == team_id):
                is_our_team = True
                is_home = (home_team_id == team_id)
                opponent = away_team if is_home else home_team
            elif team_name and (team_name.lower() == away_team.lower() or team_name.lower() == home_team.lower()):
                # Only match exact team name, not substring
                is_our_team = True
                is_home = team_name.lower() == home_team.lower()
                opponent = away_team if is_home else home_team
            
            if not is_our_team:
                continue
            
            # Parse date and time
            date_str = day.get("Name", "")
            game_time = game.get("TimeFormatted", "")
            
            date_part, _ = _parse_game_date(day.get("DateFormatted", "") or date_str)
            
            # Venue and court
            venue = game.get("VenueName", "")
            court = game.get("CourtName", "")
            
            # Division and bracket
            division = game.get("DivisionName", "")
            bracket = game.get("BracketName", "")
            round_num = game.get("Round", 0)
            
            # Scores
            home_score = game.get("HomeTeamScoreDisplay")
            away_score = game.get("AwayTeamScoreDisplay")
            
            game_info = GameInfo(
                game_id=game.get("Id", 0),
                event_id=event_id,
                event_name=event_name,
                event_slug=event_slug,
                team_name=team_name,
                opponent=opponent,
                is_home=is_home,
                date=date_part,
                time=game_time,
                venue=venue,
                court=court,
                division=division,
                bracket=bracket,
                round=round_num,
                home_score=home_score,
                away_score=away_score,
                raw_data=game,
            )
            games.append(game_info)
    
    return games


def extract_games_from_standings(html: str, event_id: int, event_name: str, event_slug: str, team_name: str) -> List[GameInfo]:
    """Extract games for a specific team from standings HTML."""
    games = []
    
    # The standings page has tables with division pools and results
    # Look for game links and extract info
    # Pattern: /eventid/event-slug/game?gameid=XXXXX
    game_links = re.findall(rf'/{event_id}/{re.escape(event_slug)}/game\?gameid=(\d+)', html)
    
    # Also look for game data in the HTML tables
    # This is complex HTML parsing - for now return empty and rely on other methods
    return games


def extract_games_from_interactive_schedule(html: str, event_id: int, event_name: str, event_slug: str, team_name: str) -> List[GameInfo]:
    """Extract games from interactive schedule HTML (loads via JS)."""
    games = []
    
    # The interactive schedule loads games via JavaScript/knockout
    # The raw HTML won't have the game data
    # We'd need a headless browser to render it
    return games


def extract_games_from_schedule_page(html: str, event_id: int, event_name: str, event_slug: str, team_name: str) -> List[GameInfo]:
    """Extract games from the main schedule page HTML."""
    games = []
    
    # Look for game links
    game_link_pattern = rf'/{event_id}/{re.escape(event_slug)}/game\?gameid=(\d+)'
    game_ids = set(re.findall(game_link_pattern, html))
    
    # The schedule page uses knockoutJS templates so data isn't in raw HTML
    # We'd need to render JavaScript to get the game data
    return games


async def extract_team_games_playwright(
    event_id: int,
    event_slug: str,
    event_name: str,
    team_name: str,
    division_id: Optional[int] = None,
) -> List[GameInfo]:
    """
    Extract games using Playwright (headless browser) to render JavaScript.
    
    Requires: pip install playwright && playwright install chromium
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("Playwright not installed. Run: pip install playwright && playwright install chromium")
        return []
    
    games = []
    url = f"https://basketball.exposureevents.com/{event_id}/{event_slug}/schedule"
    if division_id:
        url += f"?divisionid={division_id}"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(3000)  # Wait for JS to load games
            
            # Get the rendered HTML
            html = await page.content()
            
            # Extract game data from the rendered page
            # The games are in knockoutJS templates - look for game elements
            game_elements = await page.query_selector_all('[data-bind*="game"], .game-row, .schedule-game')
            
            for elem in game_elements:
                text = await elem.inner_text()
                # Parse game info from text
                # This would need custom parsing based on the actual HTML structure
                pass
            
            # Alternative: extract from network responses
            # The schedule loads games via AJAX to /eventid/event-slug/eventgames
            
        finally:
            await browser.close()
    
    return games


def get_game_ical(client: PublicExposureClient, game_id: int) -> Optional[str]:
    """Fetch iCal for a specific game."""
    return client.get_game_ical(game_id)


def parse_ical_game(ical_content: str) -> Optional[Dict[str, Any]]:
    """Parse iCal content to extract game details."""
    if not ical_content or "BEGIN:VEVENT" not in ical_content:
        return None
    
    # Simple iCal parsing
    data = {}
    lines = ical_content.split("\n")
    for line in lines:
        line = line.strip()
        if line.startswith("SUMMARY:"):
            data["summary"] = line[8:]
        elif line.startswith("DESCRIPTION:"):
            data["description"] = line[12:]
        elif line.startswith("LOCATION:"):
            data["location"] = line[9:]
        elif line.startswith("DTSTART:"):
            data["dtstart"] = line[8:]
        elif line.startswith("DTEND:"):
            data["dtend"] = line[6:]
        elif line.startswith("UID:"):
            data["uid"] = line[4:]
    
    return data


# Synchronous wrapper for playwright
def extract_team_games_with_browser(
    event_id: int,
    event_slug: str,
    event_name: str,
    team_name: str,
    division_id: Optional[int] = None,
) -> List[GameInfo]:
    """Synchronous wrapper for Playwright-based game extraction."""
    import asyncio
    return asyncio.run(extract_team_games_playwright(event_id, event_slug, event_name, team_name, division_id))