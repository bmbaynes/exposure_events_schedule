import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from .public_client import PublicExposureClient


@dataclass
class TeamMatch:
    team_id: int
    team_name: str
    division: str
    division_id: int
    event_id: int
    event_name: str
    event_slug: str
    city: str
    state: str
    raw_data: Dict[str, Any]

    @property
    def team_url(self) -> str:
        return f"https://basketball.exposureevents.com/{self.event_id}/{self.event_slug}/teams/{self.team_name.lower().replace(' ', '-')}?divisionteamid={self.team_id}"


def _parse_teams_from_html(html: str) -> List[Dict[str, Any]]:
    """Parse teams from the teams page HTML."""
    teams = []
    
    # The teams page has links like: /eventid/event-slug/teams/team-name?divisionteamid=XXXXX
    # Extract team info from the HTML
    # Pattern: href="/271591/.../teams/...?divisionteamid=5578147">Team Name</a>
    link_pattern = r'href="[^"]*/teams/[^"]*\?divisionteamid=(\d+)"[^>]*>([^<]+)</a>'
    matches = re.findall(link_pattern, html)
    
    for team_id_str, name in matches:
        teams.append({
            "Value": int(team_id_str),
            "Name": name.strip(),
            "DivisionId": 0,  # Not available from HTML
            "City": "",
            "StateRegion": "",
        })
    
    return teams


def check_team_pattern(
    client: PublicExposureClient,
    event_id: int,
    event_slug: str,
    event_name: str,
    pattern: str = "Team NSSA*RB/MI*",
) -> List[TeamMatch]:
    """
    Check if any teams in an event match the given wildcard pattern.
    
    Tries the search API endpoint first, falls back to teams page HTML parsing.
    
    Args:
        client: PublicExposureClient instance
        event_id: Exposure event ID
        event_slug: Event URL slug
        event_name: Event display name
        pattern: Wildcard pattern (supports * as wildcard)
    
    Returns:
        List of TeamMatch objects for matching teams
    """
    # Try search API first
    search_data = client.get_event_search_data(event_id, event_slug)
    
    teams = []
    divisions = {}
    
    if search_data:
        parsed = client.parse_search_data(search_data)
        teams = parsed.get("teams", [])
        divisions = {d.get("Id"): d.get("Name", "") for d in parsed.get("divisions", [])}
    else:
        # Fallback: try teams page
        teams_html = client.get_teams_html(event_id, event_slug)
        if teams_html:
            teams = _parse_teams_from_html(teams_html)
    
    if not teams:
        return []
    
    matching_teams = client.find_team_by_pattern(teams, pattern)
    
    matches = []
    for team in matching_teams:
        division_id = team.get("DivisionId", 0)
        matches.append(TeamMatch(
            team_id=team.get("Value", team.get("Id", 0)),
            team_name=team.get("Name", ""),
            division=divisions.get(division_id, ""),
            division_id=division_id,
            event_id=event_id,
            event_name=event_name,
            event_slug=event_slug,
            city=team.get("City", ""),
            state=team.get("StateRegion", ""),
            raw_data=team,
        ))
    
    return matches


def check_multiple_events(
    client: PublicExposureClient,
    events: List[Dict[str, Any]],
    pattern: str = "Team NSSA*RB/MI*",
) -> List[TeamMatch]:
    """Check multiple events for teams matching pattern."""
    all_matches = []
    for event in events:
        event_id = event.get("id") or event.get("event_id")
        event_slug = event.get("slug") or event.get("event_slug")
        event_name = event.get("name") or event.get("event_name")
        
        if event_id and event_slug:
            matches = check_team_pattern(client, event_id, event_slug, event_name, pattern)
            all_matches.extend(matches)
    
    return all_matches