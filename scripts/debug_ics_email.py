#!/usr/bin/env python3
"""
Debug script to test ICS attachment delivery via Resend.
Sends emails with progressively simpler MIME structures to isolate the issue.
"""

import os
import base64
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from email.utils import formatdate, make_msgid
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


def create_ics_attachment(ics_content: str, filename: str) -> MIMEBase:
    part = MIMEBase('text', 'calendar', method='PUBLISH', name=filename, charset='utf-8')
    payload_bytes = ics_content.encode('utf-8')
    payload_b64 = base64.b64encode(payload_bytes).decode('ascii')
    part.set_payload(payload_b64)
    part['Content-Transfer-Encoding'] = 'base64'
    part.add_header('Content-Disposition', f'attachment; filename="{filename}"')
    return part


def send_raw_via_resend(raw_message: str, subject: str) -> dict:
    """Send raw MIME message via Resend API."""
    raw_bytes = raw_message.encode('utf-8')
    raw_b64 = base64.b64encode(raw_bytes).decode('utf-8')
    
    response = resend.Emails.send({
        "from": FROM_EMAIL,
        "to": [RECEIVER_EMAIL],
        "subject": subject,
        "raw": raw_b64,
        "text": "Debug email - see subject for structure",
    })
    return response


def build_and_send(version: str, msg: MIMEMultipart, description: str):
    """Build subject and send email."""
    subject = f"[DEBUG {version}] {description}"
    msg['Subject'] = subject
    if 'From' not in msg:
        msg['From'] = FROM_EMAIL
    if 'To' not in msg:
        msg['To'] = RECEIVER_EMAIL
    msg['Date'] = formatdate(localtime=True)
    msg['Message-ID'] = make_msgid(domain='debug.exposureevents.com')
    
    raw_message = msg.as_string()
    
    print(f"\n=== Sending {version}: {description} ===")
    print(f"Subject: {subject}")
    print(f"MIME Structure:")
    for part in msg.walk():
        ct = part.get_content_type()
        disp = part.get('Content-Disposition', '')
        enc = part.get('Content-Transfer-Encoding', '')
        fn = part.get_filename() or ''
        indent = '  ' * (len(part.get('Content-Type', '').split('/')) if False else 0)
        print(f"  {ct}{f' filename={fn}' if fn else ''}{f' encoding={enc}' if enc else ''}{f' disp={disp}' if disp else ''}")
    
    try:
        response = send_raw_via_resend(raw_message, subject)
        print(f"  Resend ID: {response.get('id', 'unknown')}")
        return response
    except Exception as e:
        print(f"  ERROR: {e}")
        return None


def test_v1_full_structure():
    """V1: Full tournament structure - multipart/mixed with multipart/alternative + ICS"""
    msg = MIMEMultipart('mixed')
    
    alt = MIMEMultipart('alternative')
    text = MIMEText("Test plain text body", 'plain', 'utf-8')
    text['Content-Transfer-Encoding'] = 'quoted-printable'
    html = MIMEText("<p>Test <b>HTML</b> body</p>", 'html', 'utf-8')
    html['Content-Transfer-Encoding'] = '7bit'
    alt.attach(text)
    alt.attach(html)
    msg.attach(alt)
    
    ics_att = create_ics_attachment(ICS_CONTENT, "test_schedule.ics")
    msg.attach(ics_att)
    
    return build_and_send("V1", msg, "Full: multipart/mixed > multipart/alternative(text+html) + ICS")


def test_v2_no_html():
    """V2: No HTML part - multipart/mixed > multipart/alternative(text only) + ICS"""
    msg = MIMEMultipart('mixed')
    
    alt = MIMEMultipart('alternative')
    text = MIMEText("Test plain text body only", 'plain', 'utf-8')
    text['Content-Transfer-Encoding'] = 'quoted-printable'
    alt.attach(text)
    msg.attach(alt)
    
    ics_att = create_ics_attachment(ICS_CONTENT, "test_schedule.ics")
    msg.attach(ics_att)
    
    return build_and_send("V2", msg, "No HTML: multipart/mixed > multipart/alternative(text only) + ICS")


def test_v3_no_alternative():
    """V3: No multipart/alternative - multipart/mixed > text + ICS"""
    msg = MIMEMultipart('mixed')
    
    text = MIMEText("Test plain text body directly in mixed", 'plain', 'utf-8')
    text['Content-Transfer-Encoding'] = 'quoted-printable'
    msg.attach(text)
    
    ics_att = create_ics_attachment(ICS_CONTENT, "test_schedule.ics")
    msg.attach(ics_att)
    
    return build_and_send("V3", msg, "No alternative: multipart/mixed > text + ICS")


def test_v4_ics_only():
    """V4: Only ICS attachment - multipart/mixed > ICS only (no text body)"""
    msg = MIMEMultipart('mixed')
    
    ics_att = create_ics_attachment(ICS_CONTENT, "test_schedule.ics")
    msg.attach(ics_att)
    
    return build_and_send("V4", msg, "ICS only: multipart/mixed > ICS attachment only")


def test_v5_text_plain_mixed():
    """V5: text/plain as main body + ICS in multipart/mixed"""
    msg = MIMEMultipart('mixed')
    
    # text/plain as first part
    text = MIMEText("Test plain text body", 'plain', 'utf-8')
    text['Content-Transfer-Encoding'] = 'quoted-printable'
    msg.attach(text)
    
    ics_att = create_ics_attachment(ICS_CONTENT, "test_schedule.ics")
    msg.attach(ics_att)
    
    return build_and_send("V5", msg, "text/plain first: multipart/mixed > text/plain + ICS")


def test_v6_simple_message():
    """V6: Simple message with ICS - not multipart/mixed, just message with attachment"""
    # This creates a message that might be treated differently
    msg = MIMEMultipart()
    msg['Content-Type'] = 'multipart/mixed'
    
    text = MIMEText("Simple message with ICS", 'plain', 'utf-8')
    text['Content-Transfer-Encoding'] = 'quoted-printable'
    msg.attach(text)
    
    ics_att = create_ics_attachment(ICS_CONTENT, "test_schedule.ics")
    msg.attach(ics_att)
    
    return build_and_send("V6", msg, "Simple multipart/mixed: text + ICS (no alternative)")


def test_v7_quoted_printable_ics():
    """V7: ICS with quoted-printable encoding instead of base64"""
    msg = MIMEMultipart('mixed')
    
    text = MIMEText("Test with QP-encoded ICS", 'plain', 'utf-8')
    text['Content-Transfer-Encoding'] = 'quoted-printable'
    msg.attach(text)
    
    part = MIMEBase('text', 'calendar', method='PUBLISH', name="test_schedule.ics", charset='utf-8')
    part.set_payload(ICS_CONTENT, charset='utf-8')
    encoders.encode_quopri(part)
    part.add_header('Content-Disposition', 'attachment; filename="test_schedule.ics"')
    msg.attach(part)
    
    return build_and_send("V7", msg, "QP-encoded ICS: multipart/mixed > text + ICS (quoted-printable)")


def test_v8_no_vtimezone():
    """V8: Same as V1 but without VTIMEZONE block"""
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
    
    msg = MIMEMultipart('mixed')
    
    alt = MIMEMultipart('alternative')
    text = MIMEText("Test no VTIMEZONE", 'plain', 'utf-8')
    text['Content-Transfer-Encoding'] = 'quoted-printable'
    html = MIMEText("<p>Test <b>HTML</b> no VTIMEZONE</p>", 'html', 'utf-8')
    html['Content-Transfer-Encoding'] = '7bit'
    alt.attach(text)
    alt.attach(html)
    msg.attach(alt)
    
    ics_att = create_ics_attachment(simple_ics, "test_schedule.ics")
    msg.attach(ics_att)
    
    return build_and_send("V8", msg, "No VTIMEZONE: full structure but simple ICS")


def test_v9_no_method_publish():
    """V9: ICS without METHOD:PUBLISH"""
    no_method_ics = ICS_CONTENT.replace("METHOD:PUBLISH", "")
    msg = MIMEMultipart('mixed')
    
    text = MIMEText("Test no METHOD:PUBLISH", 'plain', 'utf-8')
    text['Content-Transfer-Encoding'] = 'quoted-printable'
    msg.attach(text)
    
    ics_att = create_ics_attachment(no_method_ics, "test_schedule.ics")
    msg.attach(ics_att)
    
    return build_and_send("V9", msg, "No METHOD:PUBLISH: text + ICS (no METHOD header)")


if __name__ == "__main__":
    resend.api_key = RESEND_API_KEY
    
    print(f"Debug ICS Email Test")
    print(f"Receiver: {RECEIVER_EMAIL}")
    print(f"Sender: {FROM_EMAIL}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    results = {}
    
    # Run all tests
    tests = [
        test_v1_full_structure,
        test_v2_no_html,
        test_v3_no_alternative,
        test_v4_ics_only,
        test_v5_text_plain_mixed,
        test_v6_simple_message,
        test_v7_quoted_printable_ics,
        test_v8_no_vtimezone,
        test_v9_no_method_publish,
    ]
    
    for test_fn in tests:
        try:
            results[test_fn.__name__] = test_fn()
        except Exception as e:
            print(f"  ERROR in {test_fn.__name__}: {e}")
            results[test_fn.__name__] = None
    
    print("\n=== SUMMARY ===")
    for name, result in results.items():
        status = "OK" if result else "FAILED"
        print(f"  {name}: {status} - Resend ID: {result.get('id') if result else 'N/A'}")