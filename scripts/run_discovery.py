#!/usr/bin/env python3
"""Script to run tournament discovery and send email itinerary."""
from exposure_events_schedule import generate_email_itinerary
from datetime import datetime

def main():
    ref_date = datetime.now()
    print(f'Running discovery for weekend of: {ref_date}')
    
    results = generate_email_itinerary(
        reference_date=ref_date,
        team_pattern='Team NSSA*RB/MI*',
        recipient_email='bmbaynes@gmail.com',
        sender_email='Tournament Tracker <tracker@r1.modogt.com>'
    )
    
    email_generated = results.get('email_generated')
    email_sent = results.get('email_sent')
    print(f'Email generated: {email_generated}')
    print(f'Email sent: {email_sent}')
    
    for email in results.get('emails_sent', []):
        event_name = email['event_name']
        total_games = email['total_games']
        sent = email['email_sent']
        print(f'  - {event_name}: {total_games} games - Sent: {sent}')
        resend_resp = email.get('resend_response')
        if resend_resp:
            resend_id = resend_resp.get('id')
            print(f'    Resend ID: {resend_id}')
    
    if not email_sent:
        print('WARNING: No emails were sent!')
        exit(1)

if __name__ == '__main__':
    main()