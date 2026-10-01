#!/usr/bin/env python3
"""
Debug script to test ICS attachment delivery via Resend using attachments parameter.
"""

import os
import base64
from datetime import datetime
import resend

RESEND_API_KEY = os.getenv("RESEND_API_KEY")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL")
FROM_EMAIL = "Tournament Tracker <tracker@r1.modogt.com>"

if not RESEND_API_KEY or not RECEIVER_EMAIL:
    print("ERROR: RESEND_API_KEY and RECEIVER_EMAIL environment variables required")
    exit(1)

ICS_CONTENT = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Debug//EN
CALSCALE:GREGORIAN
METHOD:PUBLISH
X-WR-CALNAME:Test Calendar
X-WR-TIMEZONE:America/New_York
BEGIN:VTIMEZONE
TZID:America/New_York
X-LIC-LOCATION:America/New_York
BEGIN:DAYLIGHT
TZOFFSETFROM:-0500
TZOFFSETTO:-0400
TZNAME:EDT
DTSTART:19700308T020000
RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=2SU
END:DAYLIGHT
BEGIN:STANDARD
TZOFFSETFROM:-0400
TZOFFSETTO:-0500
TZNAME:EST
DTSTART:19701101T020000
RRULE:FREQ=YEARLY;BYMONTH=11;BYDAY=1SU
END:STANDARD
END:VTIMEZONE
BEGIN:VEVENT
UID:test123@debug.com
DTSTAMP:20261001T180000Z
DTSTART;TZID=America/New_York:20261003T143000
DTEND;TZID=America/New_York:20261003T153000
SUMMARY:Test Game - Home Team vs Opponent
DESCRIPTION:Test event for debugging
LOCATION:Test Venue
STATUS:CONFIRMED
TRANSP:OPAQUE
SEQUENCE:0
END:VEVENT
END:VCALENDAR"""


def send_with_attachments(version: str, description: str, html_body: str = None, text_body: str = None, ics_content: str = None, ics_filename: str = "test_schedule.ics") -> dict:
    """Send email using Resend's attachments parameter."""
    subject = f"[DEBUG {version}] {description}"
    
    # Encode ICS as base64 for attachment
    attachment = None
    if ics_content:
        ics_b64 = base64.b64encode(ics_content.encode('utf-8')).decode('ascii')
        attachment = {
            "filename": ics_filename,
            "content": ics_b64,
        }
    
    payload = {
        "from": FROM_EMAIL,
        "to": [RECEIVER_EMAIL],
        "subject": subject,
    }
    
    if html_body:
        payload["html"] = html_body
    if text_body:
        payload["text"] = text_body
    if attachment:
        payload["attachments"] = [attachment]
    
    print(f"\n=== Sending {version}: {description} ===")
    print(f"Subject: {subject}")
    print(f"Payload keys: {list(payload.keys())}")
    if attachment:
        print(f"  Attachment: {ics_filename} ({len(ics_b64)} chars base64)")
    
    try:
        response = resend.Emails.send(payload)
        print(f"  Resend ID: {response.get('id', 'unknown')}")
        return response
    except Exception as e:
        print(f"  ERROR: {e}")
        return None


if __name__ == "__main__":
    resend.api_key = RESEND_API_KEY
    
    print(f"Debug ICS Email Test (using attachments parameter)")
    print(f"Receiver: {RECEIVER_EMAIL}")
    print(f"Sender: {FROM_EMAIL}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    results = {}
    
    # Test 1: HTML + ICS attachment
    results["A1_html_ics"] = send_with_attachments(
        "A1", "HTML + ICS attachment via attachments param",
        html_body="<p>Test <b>HTML</b> body with ICS attachment</p>",
        text_body="Test plain text body with ICS attachment",
        ics_content=ICS_CONTENT
    )
    
    # Test 2: Text only + ICS attachment
    results["A2_text_ics"] = send_with_attachments(
        "A2", "Text only + ICS attachment via attachments param",
        text_body="Test plain text body with ICS attachment",
        ics_content=ICS_CONTENT
    )
    
    # Test 3: HTML only + ICS attachment
    results["A3_html_only_ics"] = send_with_attachments(
        "A3", "HTML only + ICS attachment via attachments param",
        html_body="<p>Test <b>HTML</b> only with ICS attachment</p>",
        ics_content=ICS_CONTENT
    )
    
    # Test 4: ICS attachment only (no body)
    results["A4_ics_only"] = send_with_attachments(
        "A4", "ICS attachment only (no body)",
        ics_content=ICS_CONTENT
    )
    
    # Test 5: Simple ICS (no VTIMEZONE)
    simple_ics = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Debug//EN
CALSCALE:GREGORIAN
METHOD:PUBLISH
BEGIN:VEVENT
UID:test123@debug.com
DTSTAMP:20261001T180000Z
DTSTART:20261003T143000
DTEND:20261003T153000
SUMMARY:Test Game - Simple ICS
END:VEVENT
END:VCALENDAR"""
    
    results["A5_simple_ics"] = send_with_attachments(
        "A5", "Simple ICS (no VTIMEZONE) + text",
        text_body="Test with simple ICS (no VTIMEZONE)",
        ics_content=simple_ics
    )
    
    # Test 6: ICS with METHOD:REQUEST instead of PUBLISH
    request_ics = ICS_CONTENT.replace("METHOD:PUBLISH", "METHOD:REQUEST")
    results["A6_method_request"] = send_with_attachments(
        "A6", "METHOD:REQUEST ICS + text",
        text_body="Test with METHOD:REQUEST",
        ics_content=request_ics
    )
    
    # Test 7: ICS without METHOD header
    no_method_ics = ICS_CONTENT.replace("METHOD:PUBLISH", "")
    results["A7_no_method"] = send_with_attachments(
        "A7", "No METHOD header ICS + text",
        text_body="Test with no METHOD header",
        ics_content=no_method_ics
    )
    
    # Test 8: Different filename
    results["A8_filename"] = send_with_attachments(
        "A8", "Different filename (invite.ics) + text",
        text_body="Test with invite.ics filename",
        ics_content=ICS_CONTENT,
        ics_filename="invite.ics"
    )
    
    print("\n=== SUMMARY ===")
    for name, result in results.items():
        status = "OK" if result else "FAILED"
        print(f"  {name}: {status} - Resend ID: {result.get('id') if result else 'N/A'}")