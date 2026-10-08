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
    
    emails_generated = results.get('emails_generated', False)
    emails_sent_list = results.get('emails_sent', [])
    
    any_email_sent = any(e.get('email_sent', False) for e in emails_sent_list)
    
    print(f'Emails generated: {emails_generated}')
    print(f'Any email sent: {any_email_sent}')
    
    for email in emails_sent_list:
        event_name = email['event_name']
        total_games = email['total_games']
        sent = email['email_sent']
        print(f'  - {event_name}: {total_games} games - Sent: {sent}')
        resend_resp = email.get('resend_response')
        if resend_resp:
            resend_id = resend_resp.get('id')
            print(f'    Resend ID: {resend_id}')
    
    if not emails_generated:
        print('WARNING: No emails were generated!')
        exit(1)
    
    # Exit 0 even if no emails were actually sent (e.g., Resend not configured)
    # since the email was at least generated and saved

if __name__ == '__main__':
    main()