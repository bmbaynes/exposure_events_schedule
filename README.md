# Exposure Events Schedule

Python modules to interact with the Exposure Basketball Events API using **unauthenticated endpoints only**. No API keys required.

## Package Structure

```
exposure_events_schedule/
├── src/exposure_events_schedule/
│   ├── __init__.py              # Package exports
│   ├── public_client.py         # Unauthenticated HTTP client
│   ├── team_checker.py          # Check teams for wildcard patterns
│   ├── game_extractor.py        # Extract games (Playwright support for JS)
│   ├── main.py                  # Orchestrator with known event IDs
│   └── example_usage.py         # Demo script
```

## Setup

1. Install dependencies:
```bash
uv pip install -e .
```

2. Optional: For browser-based game extraction (Playwright):
```bash
uv pip install -e .[browser]
playwright install chromium
```

## Usage

### Find teams matching a pattern (no auth needed!)

```python
from exposure_events_schedule import (
    PublicExposureClient,
    check_team_pattern,
    extract_team_games,
)

client = PublicExposureClient()

# Search for teams in a known event (no auth needed!)
event_id = 271591
event_slug = "zero-gravity-nerr-hoop-festival"
event_name = "ZERO GRAVITY NERR Hoop Festival"

# Find teams matching wildcard pattern
matches = check_team_pattern(client, event_id, event_slug, event_name, "Team NSSA*RB/MI*")
for m in matches:
    print(f"Found: {m.team_name} (Division: {m.division})")

# Extract games (limited - static HTML only)
games = extract_team_games(client, event_id, event_slug, event_name, "Team Name")
```

### Run the example

```bash
# Find Team NSSA*RB/MI* teams in the Zero Gravity NERR Hoop Festival
uv run python -m exposure_events_schedule.example_usage
```

### Orchestrator with known events

```python
from exposure_events_schedule import run_with_known_events

results = run_with_known_events(
    event_ids=[271591, 271596],
    event_slugs=["zero-gravity-nerr-hoop-festival", "zero-gravity-battle-for-the-belt-south"],
    event_names=["ZERO GRAVITY NERR Hoop Festival", "ZERO GRAVITY Battle for the Belt South"],
    team_pattern="Team NSSA*RB/MI*",
    output_file="nssa_results.json"
)
```

## Available Unauthenticated Endpoints

| Data | Endpoint | Format |
|------|----------|--------|
| **Teams, Divisions, Locations** | `/eventid/event-slug/search?eventid=X&eventname=Y` | JSON |
| **Teams page** | `/eventid/event-slug/teams` | HTML |
| **Standings** | `/eventid/event-slug/documents/standings?type=division` | HTML |
| **Interactive schedule** | `/interactive/schedule?eventid=X` | HTML (JS-rendered) |
| **Individual game iCal** | `https://ical.exposureevents.com/calendar-game.ics?expired=TS&gameid=ID` | ICS |

## Limitations

- **Event discovery**: Public listings at `/youth-basketball-events/massachusetts` are disabled. You must provide known event IDs/slugs.
- **Game data**: Schedule pages load games via JavaScript. Static HTML extraction returns 0 games. Use:
  - Playwright/Selenium to render schedule pages (`extract_team_games_with_browser()`)
  - Individual game iCal if you know game IDs

## API Reference

Based on [Exposure Basketball Events API](https://basketball.exposureevents.com/api)

The unauthenticated endpoints used:
- `GET /{eventid}/{eventslug}/search` - Teams, divisions, locations
- `GET /{eventid}/{eventslug}/teams` - Teams page
- `GET /{eventid}/{eventslug}/documents/standings` - Standings
- `GET /interactive/schedule?eventid=X` - Interactive schedule
- `GET https://ical.exposureevents.com/calendar-game.ics` - Game iCal