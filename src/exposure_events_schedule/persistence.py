"""
Persistence and change detection for tournament schedules.
Saves previous run data and detects changes between runs.
"""

import json
import os
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict
from .game_extractor import GameInfo


@dataclass
class StoredGame:
    """Stored game data for persistence."""
    game_id: str
    event_id: int
    event_name: str
    team_name: str
    opponent: str
    is_home: bool
    date: str
    time: str
    venue: str
    court: str
    division: str
    bracket: str
    round: str
    home_score: Optional[int]
    away_score: Optional[int]
    ical_url: Optional[str]
    game_url: Optional[str]
    sequence: int = 0

    @classmethod
    def from_game_info(cls, game: GameInfo, sequence: int = 0) -> 'StoredGame':
        return cls(
            game_id=game.game_id,
            event_id=game.event_id,
            event_name=game.event_name,
            team_name=game.team_name,
            opponent=game.opponent,
            is_home=game.is_home,
            date=game.date,
            time=game.time,
            venue=game.venue,
            court=game.court,
            division=game.division,
            bracket=game.bracket,
            round=game.round,
            home_score=game.home_score,
            away_score=game.away_score,
            ical_url=game.ical_url,
            game_url=game.game_url,
            sequence=sequence,
        )

    def to_game_info(self) -> GameInfo:
        """Convert back to GameInfo (without sequence)."""
        return GameInfo(
            game_id=self.game_id,
            event_id=self.event_id,
            event_name=self.event_name,
            team_name=self.team_name,
            opponent=self.opponent,
            is_home=self.is_home,
            date=self.date,
            time=self.time,
            venue=self.venue,
            court=self.court,
            division=self.division,
            bracket=self.bracket,
            round=self.round,
            home_score=self.home_score,
            away_score=self.away_score,
            ical_url=self.ical_url,
            game_url=self.game_url,
        )

    def signature(self) -> str:
        """Unique signature for comparing games (excludes scores which change)."""
        return f"{self.game_id}|{self.date}|{self.time}|{self.venue}|{self.court}|{self.opponent}|{self.is_home}"

    def has_changed(self, other: 'StoredGame') -> bool:
        """Check if game details have changed (excluding scores)."""
        return self.signature() != other.signature()


def get_storage_path(team_pattern: str = "Team NSSA*RB/MI*") -> str:
    """Get the storage file path for a team pattern."""
    safe_pattern = team_pattern.replace("*", "_").replace("/", "_").replace("\\", "_")
    return os.path.join(os.getcwd(), "schedule_history", f"history_{safe_pattern}.json")


def load_history(team_pattern: str = "Team NSSA*RB/MI*") -> Dict[str, Any]:
    """Load previous run history from file."""
    path = get_storage_path(team_pattern)
    if not os.path.exists(path):
        return {"runs": [], "games_by_event": {}}
    
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception:
        return {"runs": [], "games_by_event": {}}


def save_history(history: Dict[str, Any], team_pattern: str = "Team NSSA*RB/MI*") -> None:
    """Save history to file."""
    path = get_storage_path(team_pattern)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        json.dump(history, f, indent=2, default=str)


def compare_games(
    current_games: List[GameInfo], 
    previous_games: List[StoredGame]
) -> Tuple[List[StoredGame], List[str]]:
    """
    Compare current games with previous games.
    Returns (updated_games_with_sequence, change_summary_lines).
    """
    prev_by_id = {g.game_id: g for g in previous_games}
    updated = []
    changes = []
    
    for game in current_games:
        prev = prev_by_id.get(game.game_id)
        
        if prev is None:
            # New game
            stored = StoredGame.from_game_info(game, sequence=0)
            updated.append(stored)
            changes.append(f"  NEW: {game.team_name} vs {game.opponent} on {game.date} at {game.time} ({game.venue})")
        else:
            # Compare signatures
            current_stored = StoredGame.from_game_info(game)
            if current_stored.signature() != prev.signature():
                # Changed game - increment sequence
                new_sequence = prev.sequence + 1
                stored = StoredGame.from_game_info(game, sequence=new_sequence)
                updated.append(stored)
                changes.append(f"  UPDATED (seq {new_sequence}): {game.team_name} vs {game.opponent} on {game.date} at {game.time}")
            else:
                # Unchanged - keep same sequence
                stored = StoredGame.from_game_info(game, sequence=prev.sequence)
                updated.append(stored)
    
    # Check for cancelled/removed games
    current_ids = {g.game_id for g in current_games}
    for prev in previous_games:
        if prev.game_id not in current_ids:
            changes.append(f"  REMOVED: {prev.team_name} vs {prev.opponent} on {prev.date} at {prev.time} (was seq {prev.sequence})")
    
    return updated, changes


def update_history(
    history: Dict[str, Any],
    events_data: Dict[str, Any],  # event_id -> {event_name, games_by_team}
    team_pattern: str,
    reference_date: datetime,
) -> Dict[str, Any]:
    """Update history with current run data and return change summaries per event."""
    run_record = {
        "timestamp": datetime.now().isoformat(),
        "reference_date": reference_date.isoformat() if reference_date else datetime.now().isoformat(),
        "team_pattern": team_pattern,
        "events": {},
    }
    
    all_changes = {}
    
    for event_id_str, event_data in events_data.items():
        event_id = int(event_id_str)
        event_name = event_data["event_name"]
        games_by_team = event_data["games_by_team"]
        
        # Flatten all games for this event
        all_current_games = []
        for team_name, games in games_by_team.items():
            all_current_games.extend(games)
        
        # Get previous games for this event
        prev_event = history.get("games_by_event", {}).get(event_id_str, {})
        prev_games = [StoredGame(**g) for g in prev_event.get("games", [])]
        
        # Compare
        updated_games, changes = compare_games(all_current_games, prev_games)
        
        # Store updated games with sequences
        history.setdefault("games_by_event", {})[event_id_str] = {
            "event_name": event_name,
            "games": [asdict(g) for g in updated_games],
        }
        
        run_record["events"][event_id_str] = {
            "event_name": event_name,
            "changes": changes,
            "has_changes": len(changes) > 0,
        }
        
        if changes:
            all_changes[event_id_str] = changes
    
    # Add run to history
    history.setdefault("runs", []).append(run_record)
    
    # Keep only last 20 runs
    history["runs"] = history["runs"][-20:]
    
    return all_changes