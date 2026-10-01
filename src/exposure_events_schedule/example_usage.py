"""
Example usage of the modules for finding Team NSSA*RB/MI* teams and games.

This script demonstrates:
1. Using the unauthenticated search endpoint to find teams
2. Checking for matching team patterns
3. (Optional) Using Playwright to extract games from rendered pages

Run with: python -m exposure_events_schedule.example_usage
"""

import json
from datetime import datetime

from . import (
    PublicExposureClient,
    check_team_pattern,
    extract_team_games,
    TeamMatch,
    GameInfo,
)


def main():
    """Run the workflow for a known event."""
    # Known event: ZERO GRAVITY NERR Hoop Festival (Oct 3-4, 2026)
    event_id = 271591
    event_slug = "zero-gravity-nerr-hoop-festival"
    event_name = "ZERO GRAVITY NERR Hoop Festival"
    team_pattern = "Team NSSA*RB/MI*"
    
    print(f"=" * 60)
    print(f"Processing event: {event_name}")
    print(f"Event ID: {event_id}")
    print(f"Team pattern: {team_pattern}")
    print(f"=" * 60)
    
    client = PublicExposureClient()
    
    # Step 1: Check for matching teams
    print("\n[1] Searching for teams matching pattern...")
    matches = check_team_pattern(client, event_id, event_slug, event_name, team_pattern)
    
    if not matches:
        print("  No matching teams found!")
        return
    
    print(f"  Found {len(matches)} matching team(s):")
    for m in matches:
        print(f"    - {m.team_name}")
        print(f"      Division ID: {m.division_id}")
        print(f"      Team ID: {m.team_id}")
        print(f"      Location: {m.city}, {m.state}")
    
    # Step 2: Try to extract games (limited without JS rendering)
    print("\n[2] Attempting to extract games from static HTML...")
    for match in matches:
        games = extract_team_games(client, event_id, event_slug, event_name, match.team_name, match.team_id)
        print(f"  {match.team_name}: {len(games)} games found from static HTML")
    
    # Step 3: Get iCal for individual games if we had game IDs
    print("\n[3] Game iCal endpoints available at:")
    print(f"    https://ical.exposureevents.com/calendar-game.ics?expired=TS&gameid=GAME_ID")
    
    # Summary
    results = {
        "event": {
            "id": event_id,
            "name": event_name,
            "slug": event_slug,
        },
        "team_pattern": team_pattern,
        "matches": [
            {
                "team_id": m.team_id,
                "team_name": m.team_name,
                "division_id": m.division_id,
                "division": m.division,
                "city": m.city,
                "state": m.state,
            }
            for m in matches
        ],
        "games": [],  # Would need Playwright or authenticated API
        "note": "Game extraction requires JavaScript rendering. Use Playwright or authenticated API.",
        "timestamp": datetime.now().isoformat(),
    }
    
    # Save results
    output_file = f"nssa_results_{event_id}.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n[4] Results saved to {output_file}")
    print(f"\nNext steps for full game data:")
    print(f"  1. Install Playwright: pip install playwright && playwright install chromium")
    print(f"  2. Then use extract_team_games_with_browser() from game_extractor")


if __name__ == "__main__":
    main()