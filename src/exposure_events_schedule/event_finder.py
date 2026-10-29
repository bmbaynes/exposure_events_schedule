"""
Event finder using unauthenticated web scraping of Exposure Events directory pages.
Finds events in MA and NH for current/upcoming weekends by scraping the search results table.
"""

import re
from datetime import datetime, timedelta
from typing import List, Optional
from dataclasses import dataclass
from playwright.sync_api import sync_playwright


@dataclass
class Event:
    id: int
    name: str
    slug: str
    organization: str
    start_date: str  # MM/DD/YYYY
    end_date: str    # MM/DD/YYYY
    city: str
    state: str
    url: str
    
    @property
    def event_url(self) -> str:
        return f"https://basketball.exposureevents.com{self.url}"
    
    @property
    def teams_url(self) -> str:
        return f"https://basketball.exposureevents.com{self.url}/teams"
    
    @property
    def search_api_url(self) -> str:
        return f"https://basketball.exposureevents.com{self.url}/search?eventid={self.id}&eventname={self.slug}"


def parse_date_range(date_str: str):
    """Parse date string like 'Oct 3-4, 2026' or 'Oct 3, 2026' or '04/10/2027 - 04/11/2027' into start/end datetime."""
    date_str = date_str.strip()
    
    # Try MM/DD/YYYY format first (what we store)
    match = re.match(r'(\d{1,2})/(\d{1,2})/(\d{4})\s*-\s*(\d{1,2})/(\d{1,2})/(\d{4})', date_str)
    if match:
        m1, d1, y1, m2, d2, y2 = match.groups()
        start = datetime(int(y1), int(m1), int(d1))
        end = datetime(int(y2), int(m2), int(d2))
        return start, end
    
    # Try single date MM/DD/YYYY
    match = re.match(r'(\d{1,2})/(\d{1,2})/(\d{4})', date_str)
    if match:
        m, d, y = match.groups()
        dt = datetime(int(y), int(m), int(d))
        return dt, dt
    
    # Try pattern with range: "Oct 3-4, 2026" or "Oct 31 - Nov 1, 2026" (cross-month)
    match = re.match(r'([A-Za-z]+)\s+(\d{1,2})\s*-\s*([A-Za-z]+)?\s*(\d{1,2}),\s*(\d{4})', date_str)
    if match:
        month_str, day1, month_str2, day2, year = match.groups()
        month = datetime.strptime(month_str[:3], "%b").month
        start = datetime(int(year), month, int(day1))
        if month_str2:
            month2 = datetime.strptime(month_str2[:3], "%b").month
            end = datetime(int(year), month2, int(day2))
        else:
            end = datetime(int(year), month, int(day2))
        return start, end
    
    # Try pattern: "Oct 3, 2026"
    match = re.match(r'([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})', date_str)
    if match:
        month_str, day, year = match.groups()
        month = datetime.strptime(month_str[:3], "%b").month
        dt = datetime(int(year), month, int(day))
        return dt, dt
    
    return None, None


def get_weekend_range(reference_date: Optional[datetime] = None):
    """Get Saturday and Sunday of the current/upcoming weekend (Monday as first day of week)."""
    if reference_date is None:
        reference_date = datetime.now()
    
    days_ahead = 5 - reference_date.weekday()  # 5 = Saturday
    saturday = (reference_date + timedelta(days=days_ahead)).replace(hour=0, minute=0, second=0, microsecond=0)
    sunday = (saturday + timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=999999)
    return saturday, sunday


def event_overlaps_weekend(start: datetime, end: datetime, saturday: datetime, sunday: datetime) -> bool:
    """Check if event overlaps with the given weekend."""
    return start <= sunday and end >= saturday


def scrape_state_events(state: str, start_date: str, end_date: Optional[str] = None, max_events: int = 100) -> List[Event]:
    """
    Scrape events for a specific state from the search results.
    
    Args:
        state: State name (e.g., 'massachusetts', 'new-hampshire')
        start_date: Start date filter in MM/DD/YYYY format
        end_date: End date filter in MM/DD/YYYY format
        max_events: Maximum number of events to return
    
    Returns:
        List of Event objects from the search results table
    """
    print(f"  scrape_state_events(state={state}, start_date={start_date}, end_date={end_date}, max_events={max_events})")
    url = f"https://basketball.exposureevents.com/youth-basketball-events/{state}"
    events = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = context.new_page()
        
        try:
            page.goto(url, wait_until='domcontentloaded', timeout=60000)
            page.wait_for_timeout(3000)
            
            # Fill start date
            page.evaluate('''(date) => {
                const input = document.getElementById('StartDateString');
                if (input) {
                    input.value = date;
                    input.dispatchEvent(new Event('change', { bubbles: true }));
                }
            }''', start_date)
            page.wait_for_timeout(1000)

            # Fill end date if provided
            if end_date:
                page.evaluate('''(date) => {
                    const input = document.getElementById('EndDateString');
                    if (input) {
                        input.value = date;
                        input.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                }''', end_date)
                page.wait_for_timeout(1000)

            # Submit form
            page.evaluate('''() => {
                const form = document.querySelector('form[data-bind*="submit: events.filter"]');
                if (form) {
                    form.dispatchEvent(new Event('submit', { bubbles: true }));
                }
            }''')
            page.wait_for_timeout(5000)
            
            # Get the full search results page HTML for parsing
            results_html = page.evaluate('''() => {
                return document.body.innerHTML;
            }''')
            print(f"  scrape_state_events({state}): retrieved {len(results_html)} chars of page HTML")
            
            events = parse_events_from_results(results_html)
            event_details = ", ".join(f"{e.name} ({e.start_date} - {e.end_date})" for e in events)
            print(f"  scrape_state_events({state}): parsed {len(events)} events from results (start={start_date}, end={end_date}): {event_details}")
            
        except Exception as e:
            print(f"  Error scraping {state}: {e}")
        finally:
            browser.close()
    
    print(f"  scrape_state_events({state}): returning {len(events[:max_events])} events")
    return events[:max_events]


def parse_events_from_results(html: str) -> List[Event]:
    """Parse event cards from the search results HTML."""
    events = []
    
    # Extract all fields using regex
    orgs = re.findall(r'<small itemprop="name" data-bind="html: OrganizationName">([^<]+)</small>', html)
    names = re.findall(r'<a href="(https://basketball\.exposureevents\.com/(\d+)/([^"]+))"[^>]*data-bind="html: Name[^>]*>([^<]+)</a>', html)
    dates = re.findall(r'data-bind="html: DateFormatted">([^<]+)</span>', html)
    cities = re.findall(r'data-bind="html: City">([^<]+)</span>', html)
    states_span = re.findall(r'data-bind="html: StateRegion">([^<]+)</span>', html)
    
    print(f"    parse_events_from_results: orgs={len(orgs)}, names={len(names)}, dates={len(dates)}, cities={len(cities)}, states={len(states_span)}")
    
    # Combine by index (all arrays should have same length except states)
    limit = min(len(orgs), len(names), len(dates), len(cities))
    if limit < max(len(orgs), len(names), len(dates), len(cities)):
        print(f"    parse_events_from_results: WARNING - array length mismatch, using min={limit}")
    
    for i in range(limit):
        org = orgs[i].strip()
        url, eid, slug, name = names[i]
        date_str = dates[i].strip()
        city = cities[i].strip()
        state = states_span[i].strip() if i < len(states_span) else ''
        
        # Parse date
        start_dt, end_dt = parse_date_range(date_str)
        if not start_dt or not end_dt:
            print(f"    parse_events_from_results: SKIP (unparseable date '{date_str}'): {name.strip()}")
            continue
        
        start_date = start_dt.strftime("%m/%d/%Y")
        end_date = end_dt.strftime("%m/%d/%Y")
        
        # Extract relative URL
        url = '/' + '/'.join(url.split('/')[3:])
        
        events.append(Event(
            id=int(eid),
            name=name.strip(),
            slug=slug,
            organization=org,
            start_date=start_date,
            end_date=end_date,
            city=city.strip(),
            state=state.upper(),
            url=url,
        ))
    
    print(f"    parse_events_from_results: returning {len(events)} events")
    return events


def find_events_ma_nh(
    reference_date: Optional[datetime] = None,
    max_events_per_state: int = 100,
) -> List[Event]:
    """
    Find all events listed on Massachusetts and New Hampshire pages for current/upcoming weekends.
    
    Args:
        reference_date: Reference date (defaults to now)
        max_events_per_state: Maximum events to scrape per state
    
    Returns:
        List of Event objects that occur on current or upcoming weekend
    """
    if reference_date is None:
        reference_date = datetime.now()
    
    saturday, sunday = get_weekend_range(reference_date)
    scrape_date = min(reference_date, saturday)
    start_date = scrape_date.strftime("%m/%d/%Y")
    
    # Scrape both states
    ma_events = scrape_state_events('massachusetts', start_date, sunday.strftime("%m/%d/%Y"), max_events_per_state)
    nh_events = scrape_state_events('new-hampshire', start_date, sunday.strftime("%m/%d/%Y"), max_events_per_state)
    
    all_events = ma_events + nh_events
    
    # Deduplicate by event ID
    seen_ids = set()
    unique_events = []
    for event in all_events:
        if event.id not in seen_ids:
            seen_ids.add(event.id)
            unique_events.append(event)
    
    # Filter for current/upcoming weekend
    next_saturday = saturday + timedelta(days=7)
    next_sunday = sunday + timedelta(days=7)
    
    print(f"  find_events_ma_nh: filtering {len(unique_events)} unique events for weekend {saturday:%m/%d/%Y}-{sunday:%m/%d/%Y} (next: {next_saturday:%m/%d/%Y}-{next_sunday:%m/%d/%Y})")
    
    weekend_events = []
    for event in unique_events:
        start_dt, end_dt = parse_date_range(f"{event.start_date} - {event.end_date}")
        if not start_dt or not end_dt:
            print(f"    SKIP (unparseable dates): {event.name} ({event.start_date} - {event.end_date}) [{event.city}, {event.state}]")
            continue
            
        is_current = event_overlaps_weekend(start_dt, end_dt, saturday, sunday)
        is_next = event_overlaps_weekend(start_dt, end_dt, next_saturday, next_sunday)
        
        print(f"    {event.name} ({event.start_date} - {event.end_date}) [{event.city}, {event.state}] [{event.organization}] -> current_weekend={is_current}, next_weekend={is_next}")
            
        if is_current:
            event.is_current_weekend = True
            event.is_upcoming_weekend = False
            weekend_events.append(event)
        elif is_next:
            event.is_current_weekend = False
            event.is_upcoming_weekend = True
            weekend_events.append(event)
    
    print(f"  find_events_ma_nh: {len(weekend_events)} events match current/upcoming weekend")
    return weekend_events


if __name__ == "__main__":
    # Test the scraper
    events = find_events_ma_nh()
    print(f"Found {len(events)} events this/next weekend in MA/NH:")
    for evt in events:
        print(f"  {evt.name} ({evt.start_date} - {evt.end_date}) - {evt.city}, {evt.state} [{evt.organization}]")
        print(f"    ID: {evt.id}, Slug: {evt.slug}")
        print(f"    URL: {evt.event_url}")