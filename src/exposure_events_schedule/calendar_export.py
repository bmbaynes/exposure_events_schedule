"""
Calendar export functionality - converts games to ICS format for Google Calendar import
and generates email-ready MIME messages with ICS attachments for auto-import.
"""

import re
import os
from typing import List, Optional
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from email.utils import formatdate, make_msgid
from .game_extractor import GameInfo


def format_ics_datetime(date_str: str, time_str: str) -> str:
    """Format date and time for ICS (YYYYMMDDTHHMMSS)."""
    # Handle time strings like "2:30 PM EDT" - remove timezone suffix
    time_str = time_str.split()[0] + " " + time_str.split()[1] if len(time_str.split()) >= 2 else time_str
    time_str = time_str.replace(" EDT", "").replace(" EST", "").replace(" PDT", "").replace(" PST", "")
    dt = datetime.strptime(f"{date_str} {time_str}", "%m/%d/%Y %I:%M %p")
    return dt.strftime("%Y%m%dT%H%M%S")


def parse_game_duration(time_str: str) -> timedelta:
    """Estimate game duration. Default to 1 hour for basketball games."""
    # Could be enhanced to parse actual game duration if available
    return timedelta(hours=1)


def format_game_time_range(date_str: str, time_str: str) -> str:
    """Format game time range as 'MM/DD/YYYY HH:MM AM/PM - HH:MM AM/PM'."""
    start_dt = format_ics_datetime(date_str, time_str)
    start_datetime = datetime.strptime(start_dt, "%Y%m%dT%H%M%S")
    end_datetime = start_datetime + parse_game_duration(time_str)
    start_display = start_datetime.strftime("%m/%d/%Y %I:%M %p")
    end_display = end_datetime.strftime("%I:%M %p")
    return f"{start_display} - {end_display}"


def escape_ics_text(text: str) -> str:
    """Escape special characters for ICS format per RFC 5545."""
    # Replace backslash first, then comma, semicolon, newline
    return text.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")


def create_ics_attachment(ics_content: str, filename: str) -> MIMEBase:
    """Create a MIME attachment for an ICS file using quoted-printable encoding."""
    part = MIMEBase('text', 'calendar', method='PUBLISH', name=filename)
    part.set_payload(ics_content, charset='utf-8')
    # Remove any default Content-Transfer-Encoding header
    if 'Content-Transfer-Encoding' in part:
        del part['Content-Transfer-Encoding']
    encoders.encode_quopri(part)
    part.add_header('Content-Disposition', f'attachment; filename="{filename}"')
    return part


def generate_ics_event(game: GameInfo, team_name: str, dt_stamp: str, organizer_email: Optional[str] = None, attendee_email: Optional[str] = None) -> str:
    """Generate a single VEVENT for a game."""
    start_dt = format_ics_datetime(game.date, game.time)
    start_datetime = datetime.strptime(start_dt, "%Y%m%dT%H%M%S")
    end_datetime = start_datetime + parse_game_duration(game.time)
    end_dt = end_datetime.strftime("%Y%m%dT%H%M%S")

    opponent = game.opponent
    is_home = game.is_home
    location = f"{game.venue}, {game.court}"

    summary = f"{'🏠' if is_home else '✈️'} {team_name} vs {opponent}"
    description = (
        f"Event: {game.event_name}\n"
        f"Division: {game.division}\n"
        f"Bracket: {game.bracket}\n"
        f"Round: {game.round}\n"
        f"Location: {location}\n"
        f"Opponent: {opponent}\n"
        f"Home/Away: {'Home' if is_home else 'Away'}\n"
        f"Game URL: https://basketball.exposureevents.com/{game.event_id}/{game.event_slug}/game?gameid={game.game_id}"
    )

    lines = [
        "BEGIN:VEVENT",
        f"UID:{game.game_id}@exposureevents.com",
        f"DTSTAMP:{dt_stamp}",
        f"DTSTART:{start_dt}",
        f"DTEND:{end_dt}",
        f"SUMMARY:{escape_ics_text(summary)}",
        f"DESCRIPTION:{escape_ics_text(description)}",
        f"LOCATION:{escape_ics_text(location)}",
        "STATUS:CONFIRMED",
        "TRANSP:OPAQUE",
        "SEQUENCE:0",
    ]
    
    if organizer_email:
        # Extract email address from "Name <email@domain.com>" format
        import re
        email_match = re.search(r'<([^>]+)>', organizer_email)
        organizer_addr = email_match.group(1) if email_match else organizer_email
        lines.append(f"ORGANIZER;CN=Basketball Schedule:mailto:{organizer_addr}")
    if attendee_email:
        lines.append(f"ATTENDEE;CN=Player;RSVP=TRUE:mailto:{attendee_email}")
    
    lines.append("END:VEVENT")
    return "\r\n".join(lines)


def games_to_ics(
    games: List[GameInfo], 
    team_name: str, 
    calendar_name: str = "Exposure Events Schedule",
    method: str = "REQUEST"
) -> str:
    """Convert a list of games to ICS format."""
    dt_stamp = datetime.now().strftime("%Y%m%dT%H%M%SZ")
    ics_lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Exposure Events//Basketball Schedule//EN",
        "CALSCALE:GREGORIAN",
        f"METHOD:{method}",
        f"X-WR-CALNAME:{escape_ics_text(calendar_name)}",
        f"X-WR-TIMEZONE:America/New_York",
        f"X-WR-RELCALID:{team_name.replace(' ', '_').lower()}@exposureevents.com",
    ]

    for game in games:
        ics_lines.append(generate_ics_event(game, team_name, dt_stamp))

    ics_lines.append("END:VCALENDAR")
    return "\r\n".join(ics_lines)


def games_to_ics_all_teams(
    games_by_team: dict,  # {team_name: [GameInfo, ...]}
    event_name: str, 
    calendar_name: str = "Exposure Events Schedule",
    method: str = "REQUEST",
    organizer_email: Optional[str] = None,
    attendee_email: Optional[str] = None,
) -> str:
    """Convert games from all teams into a single ICS format."""
    dt_stamp = datetime.now().strftime("%Y%m%dT%H%M%SZ")
    ics_lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Exposure Events//Basketball Schedule//EN",
        "CALSCALE:GREGORIAN",
        f"METHOD:{method}",
        f"X-WR-CALNAME:{escape_ics_text(calendar_name)}",
        f"X-WR-TIMEZONE:America/New_York",
        f"X-WR-RELCALID:{event_name.replace(' ', '_').lower()}@exposureevents.com",
    ]

    # Combine all games from all teams
    all_games = []
    for team_name, games in games_by_team.items():
        for game in games:
            all_games.append((team_name, game))
    
    for team_name, game in all_games:
        ics_lines.append(generate_ics_event(game, team_name, dt_stamp, organizer_email, attendee_email))

    ics_lines.append("END:VCALENDAR")
    return "\r\n".join(ics_lines)


def create_email_itinerary(
    games_by_team: dict,  # {team_name: [GameInfo, ...]}
    event_name: str,
    event_date_range: str,
    recipient_email: Optional[str] = None,
    sender_email: Optional[str] = None,
    subject: Optional[str] = None,
) -> MIMEMultipart:
    """
    Create a complete email message with a single ICS attachment containing all games for all teams.
    
    This generates a proper MIME multipart message with:
    - multipart/alternative for text/plain and text/html
    - application/ics attachment
    - Proper headers for calendar auto-import (like airline itineraries)
    """
    # Top-level multipart/mixed for attachment
    msg = MIMEMultipart('mixed')
    
    # Headers
    msg['Subject'] = subject or f"Basketball Schedule: {event_name} ({event_date_range})"
    if sender_email:
        msg['From'] = sender_email
    if recipient_email:
        msg['To'] = recipient_email
    msg['Date'] = formatdate(localtime=True)
    msg['Message-ID'] = make_msgid(domain='exposureevents.com')
    
    # Headers for calendar auto-import (like airline itineraries)
    msg['Content-Class'] = 'urn:content-classes:calendarmessage'
    
    # Create multipart/alternative for text and HTML
    alt_part = MIMEMultipart('alternative')
    
    # Create HTML body with schema.org/Event structured data for Gmail auto-calendar
    html_parts = [
        '<div itemscope itemtype="http://schema.org/SportsEvent">',
        f'<meta itemprop="name" content="Basketball Tournament: {event_name}">',
        f'<meta itemprop="startDate" content="{event_date_range.split(" - ")[0]}">',
        f'<meta itemprop="endDate" content="{event_date_range.split(" - ")[1]}">',
        f'<meta itemprop="description" content="Basketball tournament schedule for {event_name}">',
        f"<h2>Basketball Tournament Schedule: {event_name}</h2>",
        f"<p><strong>Date Range:</strong> {event_date_range}</p>",
        f"<p>This email contains a calendar attachment with all games for your teams. "
        f"Open the attachment to add all games to your calendar automatically.</p>",
        "<hr>",
    ]
    
    text_parts = [
        f"Basketball Tournament Schedule: {event_name}",
        f"Date Range: {event_date_range}",
        f"This email contains a calendar attachment with all games for your teams.",
        "Open the attachment to add all games to your calendar automatically.",
        "-" * 60,
    ]
    
    def _parse_to_iso8601(date_str: str, time_str: str) -> str:
        """Convert MM/DD/YYYY date and HH:MM AM/PM time to ISO 8601 format."""
        # Parse date: MM/DD/YYYY
        month, day, year = date_str.split('/')
        # Parse time: HH:MM AM/PM
        time_part = time_str.replace(" EDT", "").replace(" EST", "").replace(" PDT", "").replace(" PST", "")
        time_only, am_pm = time_part.split()
        hour, minute = time_only.split(':')
        hour = int(hour)
        if am_pm == 'PM' and hour != 12:
            hour += 12
        elif am_pm == 'AM' and hour == 12:
            hour = 0
        # Format as ISO 8601 with timezone offset (-04:00 for EDT)
        return f"{year}-{month}-{day}T{hour:02d}:{minute}:00-04:00"

    for team_name, games in games_by_team.items():
        html_parts.append(f'<div itemscope itemtype="http://schema.org/SportsTeam"><h3><span itemprop="name">{team_name}</span> ({len(games)} games)</h3></div>')
        html_parts.append("<ul>")
        for g in games:
            time_range = format_game_time_range(g.date, g.time)
            # Generate ISO 8601 dates for schema.org
            start_dt_iso = _parse_to_iso8601(g.date, g.time)
            end_dt_iso = _parse_to_iso8601(g.date, format_game_time_range(g.date, g.time).split(" - ")[1].strip())
            
            html_parts.append(
                f'<li itemscope itemtype="http://schema.org/SportsEvent">'
                f'<meta itemprop="name" content="{team_name} vs {g.opponent}">'
                f'<meta itemprop="startDate" content="{start_dt_iso}">'
                f'<meta itemprop="endDate" content="{end_dt_iso}">'
                f'<meta itemprop="location" content="{g.venue}, {g.court}">'
                f'<meta itemprop="description" content="{g.event_name} - {g.division}">'
                f'<strong itemprop="startDate" content="{start_dt_iso}">{time_range}</strong> - '
                f'{"Home" if g.is_home else "Away"} vs {g.opponent} '
                f'@ <span itemprop="location">{g.venue} ({g.court})</span>'
                f'</li>'
            )
        html_parts.append("</ul>")
        
        text_parts.append(f"\n{team_name} ({len(games)} games):")
        for g in games:
            time_range = format_game_time_range(g.date, g.time)
            text_parts.append(
                f"  {time_range} - "
                f"{'Home' if g.is_home else 'Away'} vs {g.opponent} "
                f"@ {g.venue} ({g.court})"
            )
    
    text_parts.append("\nThe attached .ics file contains all games for all teams above.")
    
    html_parts.append("</div>")  # Close SportsEvent
    
    # Add text and HTML parts to alternative (use 8bit encoding for HTML to prevent line breaks)
    from email.charset import QP, Charset
    utf8_charset = Charset('utf-8')
    utf8_charset.body_encoding = QP
    
    text_content = "\n".join(text_parts)
    text_part = MIMEText(text_content, 'plain', utf8_charset)
    alt_part.attach(text_part)
    
    html_content = "\n".join(html_parts)
    html_charset = Charset('utf-8')
    html_charset.body_encoding = None  # Use 8bit - no line wrapping
    html_part = MIMEText(html_content, 'html', html_charset)
    alt_part.attach(html_part)
    
    # Add alternative part to mixed message
    msg.attach(alt_part)
    
    # Add single ICS attachment with all games from all teams
    safe_event = re.sub(r'[<>:"/\\|?*]', '_', event_name)
    ics_content = games_to_ics_all_teams(
        games_by_team, 
        event_name, 
        f"{event_name} - Full Schedule", 
        method="PUBLISH",
        organizer_email=sender_email,
        attendee_email=recipient_email,
    )
    ics_attachment = create_ics_attachment(
        ics_content, 
        f"{safe_event}_schedule.ics"
    )
    msg.attach(ics_attachment)
    
    return msg


def save_email_itinerary(msg: MIMEMultipart, filepath: str) -> None:
    """Save the email message to a file (for testing/sending later)."""
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(msg.as_string())


def send_email_itinerary(msg: MIMEMultipart, smtp_host: str, smtp_port: int, 
                          username: str, password: str, use_tls: bool = True) -> None:
    """Send the email itinerary via SMTP."""
    import smtplib
    with smtplib.SMTP(smtp_host, smtp_port) as server:
        if use_tls:
            server.starttls()
        server.login(username, password)
        server.send_message(msg)


def save_ics_file(ics_content: str, filename: str) -> None:
    """Save ICS content to a file. Sanitizes filename for filesystem compatibility."""
    safe_filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    safe_filename = re.sub(r'\s+', '_', safe_filename)
    if not safe_filename.endswith('.ics'):
        safe_filename += '.ics'
    with open(filename, "w", encoding="utf-8") as f:
        f.write(ics_content)


def send_email_via_resend(
    msg: MIMEMultipart,
    api_key: Optional[str] = None,
    from_email: str = "Tournament Tracker <tracker@r1.modogt.com>",
    to_emails: List[str] = None,
) -> Optional[dict]:
    """
    Send the email itinerary via Resend API.
    
    Skips sending if RESEND_API_KEY or RECEIVER_EMAIL environment variables are not set.
    
    Args:
        msg: The MIMEMultipart message to send
        api_key: Resend API key (defaults to RESEND_API_KEY env var)
        from_email: Sender email address
        to_emails: List of recipient email addresses
        
    Returns:
        Resend API response dict, or None if skipped
    """
    api_key = api_key or os.getenv("RESEND_API_KEY")
    if not api_key:
        print("Skipping email send: RESEND_API_KEY environment variable not set")
        return None
    
    if to_emails is None:
        to_emails = []
        recipient_email = os.getenv("RECEIVER_EMAIL")
        if recipient_email:
            to_emails.append(recipient_email)
    
    if not to_emails:
        print("Skipping email send: RECEIVER_EMAIL environment variable not set")
        return None
    
    # Use raw MIME message to preserve calendar headers, but also provide html/text as fallback
    import resend
    import base64
    resend.api_key = api_key
    
    raw_message = msg.as_string()
    raw_bytes = raw_message.encode('utf-8')
    raw_b64 = base64.b64encode(raw_bytes).decode('utf-8')
    
    # Extract html and text for Resend (required even with raw)
    html_body = ""
    text_body = ""
    
    for part in msg.walk():
        content_type = part.get_content_type()
        if content_type == 'text/html':
            html_body = part.get_payload(decode=True).decode('utf-8')
        elif content_type == 'text/plain':
            text_body = part.get_payload(decode=True).decode('utf-8')
    
    try:
        response = resend.Emails.send({
            "from": from_email,
            "to": to_emails,
            "subject": msg.get('Subject', 'Basketball Tournament Schedule'),
            "raw": raw_b64,
            "html": html_body,
            "text": text_body,
        })
        return response
    except Exception as e:
        raise RuntimeError(f"Failed to send email via Resend: {e}")


def send_itinerary_via_resend(
    games_by_team: dict,
    event_name: str,
    event_date_range: str,
    to_emails: List[str],
    api_key: Optional[str] = None,
    from_email: str = "Tournament Tracker <tracker@r1.modogt.com>",
    recipient_email: Optional[str] = None,
    sender_email: Optional[str] = None,
    subject: Optional[str] = None,
) -> dict:
    """
    Create and send an email itinerary via Resend in one call.
    
    Args:
        games_by_team: Dict mapping team names to lists of GameInfo
        event_name: Name of the tournament/event
        event_date_range: Date range string
        to_emails: List of recipient email addresses
        api_key: Resend API key (defaults to RESEND_API_KEY env var)
        from_email: Sender email address
        recipient_email: Single recipient (deprecated, use to_emails)
        sender_email: Sender email (deprecated, use from_email)
        subject: Email subject
        
    Returns:
        Resend API response dict
    """
    # Handle deprecated parameters
    if recipient_email and not to_emails:
        to_emails = [recipient_email]
    if sender_email:
        from_email = sender_email
    
    if not to_emails:
        raise ValueError("At least one recipient email required (to_emails or recipient_email)")
    
    # Create the email message
    msg = create_email_itinerary(
        games_by_team=games_by_team,
        event_name=event_name,
        event_date_range=event_date_range,
        recipient_email=to_emails[0] if to_emails else None,
        sender_email=from_email,
        subject=subject,
    )
    
    # Send via Resend
    return send_email_via_resend(msg, api_key=api_key, from_email=from_email, to_emails=to_emails)