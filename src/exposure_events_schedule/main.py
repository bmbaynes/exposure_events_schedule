"""
Main orchestrator for finding Team NSSA*RB/MI* teams and their games.
Supports both known event IDs and automatic event discovery via web scraping.
"""

import json
import os
from typing import List, Dict, Any, Optional
from datetime import datetime

from . import (
    PublicExposureClient,
    check_team_pattern,
    TeamMatch,
    extract_team_games,
    GameInfo,
    find_events_ma_nh,
    Event,
    create_email_itinerary,
    save_email_itinerary,
    games_to_ics,
    save_ics_file,
)
from .calendar_export import send_email_via_resend


def run_with_known_events(
    event_ids: List[int],
    event_slugs: List[str],
    event_names: List[str],
    team_pattern: str = "Team NSSA*RB/MI*",
    output_file: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run workflow with known event IDs/slugs (bypasses event discovery).
    
    Args:
        event_ids: List of event IDs
        event_slugs: List of event URL slugs (same order as event_ids)
        event_names: List of event names (same order)
        team_pattern: Wildcard pattern to match team names
        output_file: Optional JSON file to save results
    """
    results = {
        "timestamp": datetime.now().isoformat(),
        "team_pattern": team_pattern,
        "events_checked": [],
        "team_matches": [],
        "games": [],
    }
    
    public_client = PublicExposureClient()
    
    for event_id, event_slug, event_name in zip(event_ids, event_slugs, event_names):
        print(f"\nProcessing event: {event_name} (ID: {event_id})")
        results["events_checked"].append({
            "event_id": event_id,
            "event_name": event_name,
            "event_slug": event_slug,
        })
        
        # Check for matching teams
        matches = check_team_pattern(public_client, event_id, event_slug, event_name, team_pattern)
        
        for match in matches:
            print(f"  Found matching team: {match.team_name} ({match.division})")
            results["team_matches"].append({
                "team_id": match.team_id,
                "team_name": match.team_name,
                "division": match.division,
                "division_id": match.division_id,
                "event_id": match.event_id,
                "event_name": match.event_name,
                "event_slug": match.event_slug,
            })
            
            # Extract games for this team
            games = extract_team_games(public_client, event_id, event_slug, event_name, match.team_name, match.team_id)
            
            for game in games:
                print(f"    Game: {game.date} {game.time} vs {game.opponent} @ {game.venue}")
                results["games"].append({
                    "game_id": game.game_id,
                    "event_id": game.event_id,
                    "event_name": game.event_name,
                    "team_name": game.team_name,
                    "opponent": game.opponent,
                    "is_home": game.is_home,
                    "date": game.date,
                    "time": game.time,
                    "venue": game.venue,
                    "court": game.court,
                    "division": game.division,
                    "bracket": game.bracket,
                    "round": game.round,
                    "home_score": game.home_score,
                    "away_score": game.away_score,
                    "ical_url": game.ical_url,
                    "game_url": game.game_url,
                })
    
    if output_file:
        with open(output_file, "w") as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\nResults saved to {output_file}")
    
    return results


def run_auto_discovery(
    reference_date: Optional[datetime] = None,
    team_pattern: str = "Team NSSA*RB/MI*",
    output_file: Optional[str] = None,
    max_events_per_state: int = 100,
) -> Dict[str, Any]:
    """
    Run workflow with automatic event discovery via web scraping.
    
    Args:
        reference_date: Reference date for weekend filtering (defaults to now)
        team_pattern: Wildcard pattern to match team names
        output_file: Optional JSON file to save results
        max_events_per_state: Maximum events to scrape per state
    """
    results = {
        "timestamp": datetime.now().isoformat(),
        "team_pattern": team_pattern,
        "reference_date": reference_date.isoformat() if reference_date else datetime.now().isoformat(),
        "events_checked": [],
        "team_matches": [],
        "games": [],
    }
    
    print(f"Discovering events for weekend of {reference_date or datetime.now()}")
    
    # Discover events
    events = find_events_ma_nh(reference_date=reference_date, max_events_per_state=max_events_per_state)
    
    if not events:
        print("No events found for the specified weekend")
        if output_file:
            with open(output_file, "w") as f:
                json.dump(results, f, indent=2, default=str)
        return results
    
    print(f"Found {len(events)} events for the weekend:")
    for evt in events:
        print(f"  - {evt.name} ({evt.start_date} - {evt.end_date}) [{evt.organization}]")
    
    public_client = PublicExposureClient()
    
    for evt in events:
        print(f"\nProcessing event: {evt.name} (ID: {evt.id})")
        results["events_checked"].append({
            "event_id": evt.id,
            "event_name": evt.name,
            "event_slug": evt.slug,
            "start_date": evt.start_date,
            "end_date": evt.end_date,
            "organization": evt.organization,
        })
        
        # Check for matching teams
        matches = check_team_pattern(public_client, evt.id, evt.slug, evt.name, team_pattern)
        
        if not matches:
            print(f"  No matching teams found")
            continue
            
        for match in matches:
            print(f"  Found matching team: {match.team_name} ({match.division})")
            results["team_matches"].append({
                "team_id": match.team_id,
                "team_name": match.team_name,
                "division": match.division,
                "division_id": match.division_id,
                "event_id": match.event_id,
                "event_name": match.event_name,
                "event_slug": match.event_slug,
            })
            
            # Extract games for this team
            games = extract_team_games(public_client, evt.id, evt.slug, evt.name, match.team_name, match.team_id, match.division_id)
            
            for game in games:
                print(f"    Game: {game.date} {game.time} vs {game.opponent} @ {game.venue}")
                results["games"].append({
                    "game_id": game.game_id,
                    "event_id": game.event_id,
                    "event_name": game.event_name,
                    "team_name": game.team_name,
                    "opponent": game.opponent,
                    "is_home": game.is_home,
                    "date": game.date,
                    "time": game.time,
                    "venue": game.venue,
                    "court": game.court,
                    "division": game.division,
                    "bracket": game.bracket,
                    "round": game.round,
                    "home_score": game.home_score,
                    "away_score": game.away_score,
                    "ical_url": game.ical_url,
                    "game_url": game.game_url,
                })
    
    if output_file:
        with open(output_file, "w") as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\nResults saved to {output_file}")
    
    return results


def generate_email_itinerary(
    reference_date: Optional[datetime] = None,
    team_pattern: str = "Team NSSA*RB/MI*",
    output_file: Optional[str] = None,
    recipient_email: Optional[str] = None,
    sender_email: Optional[str] = None,
    max_events_per_state: int = 100,
) -> Dict[str, Any]:
    """
    Run auto-discovery and generate an email itinerary with ICS attachments per tournament.
    
    Sends one email per tournament that has games for the matching teams.
    If no games are found in a particular tournament, no email is sent for that tournament.
    
    Args:
        reference_date: Reference date for weekend filtering (defaults to now)
        team_pattern: Wildcard pattern to match team names
        output_file: Optional file to save the email message (.eml format)
        recipient_email: Email address of recipient (for To header)
        sender_email: Email address of sender (for From header)
        max_events_per_state: Maximum events to scrape per state
    """
    results = {
        "timestamp": datetime.now().isoformat(),
        "team_pattern": team_pattern,
        "reference_date": reference_date.isoformat() if reference_date else datetime.now().isoformat(),
        "events_checked": [],
        "team_matches": [],
        "games_by_team": {},
        "emails_sent": [],
    }
    
    print(f"Discovering events for weekend of {reference_date or datetime.now()}")
    
    # Discover events
    events = find_events_ma_nh(reference_date=reference_date, max_events_per_state=max_events_per_state)
    
    if not events:
        print("No events found for the specified weekend")
        return results
    
    print(f"Found {len(events)} events for the weekend:")
    for evt in events:
        print(f"  - {evt.name} ({evt.start_date} - {evt.end_date}) [{evt.organization}]")
    
    public_client = PublicExposureClient()
    
    for evt in events:
        print(f"\nProcessing event: {evt.name} (ID: {evt.id})")
        event_info = {
            "event_id": evt.id,
            "event_name": evt.name,
            "event_slug": evt.slug,
            "start_date": evt.start_date,
            "end_date": evt.end_date,
            "organization": evt.organization,
        }
        results["events_checked"].append(event_info)
        
        # Check for matching teams
        matches = check_team_pattern(public_client, evt.id, evt.slug, evt.name, team_pattern)
        
        if not matches:
            print(f"  No matching teams found")
            continue
            
        # Collect all games for this event across all matching teams
        event_games_by_team = {}
        
        for match in matches:
            print(f"  Found matching team: {match.team_name} ({match.division})")
            results["team_matches"].append({
                "team_id": match.team_id,
                "team_name": match.team_name,
                "division": match.division,
                "division_id": match.division_id,
                "event_id": match.event_id,
                "event_name": match.event_name,
                "event_slug": match.event_slug,
            })
            
            # Extract games for this team
            games = extract_team_games(public_client, evt.id, evt.slug, evt.name, match.team_name, match.team_id, match.division_id)
            
            if games:
                if match.team_name not in event_games_by_team:
                    event_games_by_team[match.team_name] = []
                event_games_by_team[match.team_name].extend(games)
                
                for game in games:
                    print(f"    Game: {game.date} {game.time} vs {game.opponent} @ {game.venue}")
        
        # If this event has games for matching teams, send an email for this tournament
        if event_games_by_team:
            print(f"\n  Generating email for tournament: {evt.name}")
            
            email_msg = create_email_itinerary(
                games_by_team=event_games_by_team,
                event_name=evt.name,
                event_date_range=f"{evt.start_date} - {evt.end_date}",
                recipient_email=recipient_email,
                sender_email=sender_email,
            )
            
            # Save .eml file if requested
            event_output_file = None
            if output_file:
                # Create event-specific filename
                base, ext = os.path.splitext(output_file)
                event_output_file = f"{base}_{evt.slug}{ext}"
                save_email_itinerary(email_msg, event_output_file)
                event_output_file = event_output_file
                print(f"  Email itinerary saved to {event_output_file}")
            
            # Send via Resend if environment variables are configured
            send_result = send_email_via_resend(email_msg)
            email_sent = send_result is not None
            
            if send_result:
                print(f"  Email sent via Resend for tournament: {evt.name}")
            else:
                print(f"  Email not sent (RESEND_API_KEY or RECEIVER_EMAIL not configured)")
            
            results["emails_sent"].append({
                "event_id": evt.id,
                "event_name": evt.name,
                "event_slug": evt.slug,
                "teams": list(event_games_by_team.keys()),
                "total_games": sum(len(g) for g in event_games_by_team.values()),
                "email_sent": email_sent,
                "output_file": event_output_file,
                "resend_response": send_result,
            })
    
    # Build aggregated games_by_team for results
    all_games_by_team = {}
    for evt in events:
        matches = check_team_pattern(public_client, evt.id, evt.slug, evt.name, team_pattern)
        for match in matches:
            games = extract_team_games(public_client, evt.id, evt.slug, evt.name, match.team_name, match.team_id, match.division_id)
            if games:
                if match.team_name not in all_games_by_team:
                    all_games_by_team[match.team_name] = []
                all_games_by_team[match.team_name].extend(games)
    
    for team_name, games in all_games_by_team.items():
        results["games_by_team"][team_name] = [
            {
                "game_id": g.game_id,
                "event_id": g.event_id,
                "event_name": g.event_name,
                "team_name": g.team_name,
                "opponent": g.opponent,
                "is_home": g.is_home,
                "date": g.date,
                "time": g.time,
                "venue": g.venue,
                "court": g.court,
                "division": g.division,
                "bracket": g.bracket,
                "round": g.round,
            }
            for g in games
        ]
    
    results["emails_generated"] = len(results["emails_sent"]) > 0
    
    return results


if __name__ == "__main__":
    # Example usage:
    # 1. With known events:
    # run_with_known_events(
    #     event_ids=[271591],
    #     event_slugs=["zero-gravity-nerr-hoop-festival"],
    #     event_names=["ZERO GRAVITY NERR Hoop Festival"],
    #     output_file="nssa_results.json"
    # )
    
    # 2. Auto-discovery for current/upcoming weekend:
    # run_auto_discovery(output_file="nssa_results.json")
    
    # 3. Auto-discovery for specific date:
    # from datetime import datetime
    # run_auto_discovery(reference_date=datetime(2027, 4, 10), output_file="nssa_results.json")
    
    # 4. Generate email itinerary (Gmail auto-import like airline itineraries):
    # from datetime import datetime
    # generate_email_itinerary(
    #     reference_date=datetime(2026, 10, 1),
    #     output_file="nssa_itinerary.eml",
    #     recipient_email="parent@example.com",
    #     sender_email="coach@example.com"
    # )
    
    print("Usage:")
    print("  1. Known events: run_with_known_events(event_ids=[...], event_slugs=[...], event_names=[...])")
    print("  2. Auto-discovery (current weekend): run_auto_discovery()")
    print("  3. Auto-discovery (specific date): run_auto_discovery(reference_date=datetime(2027, 4, 10))")
    print("  4. Email itinerary (Gmail auto-import): generate_email_itinerary(reference_date=datetime(2026, 10, 1), output_file='itinerary.eml')")