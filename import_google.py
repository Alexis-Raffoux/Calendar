import os
import json
import pickle
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from datetime import datetime, timedelta, date
import pytz
from dotenv import load_dotenv
from icalendar import Calendar

SCOPES = ['https://www.googleapis.com/auth/calendar']

load_dotenv()

calendar_mappings = os.getenv("CALENDAR_MAPPINGS", "{}")
CALENDAR_IDS = json.loads(calendar_mappings)

def get_google_calendar_service():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = Flow.from_client_secrets_file(
                'credentials.json',
                scopes=SCOPES,
                redirect_uri='urn:ietf:wg:oauth:2.0:oob')

            auth_url, _ = flow.authorization_url(prompt='consent')
            print(f'Please go to this URL and authorize the application: {auth_url}')
            
            code = input('Enter the authorization code: ')
            flow.fetch_token(code=code)
            creds = flow.credentials

        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    
    return build('calendar', 'v3', credentials=creds)

def clear_calendar_range(service, calendar_id, start_date, end_date):
    print(f"Clearing events from calendar {calendar_id} between {start_date} and {end_date}")
    
    # Add a day to end_date to ensure we catch all events on the last day
    end_date += timedelta(days=1)
    
    # Ensure dates are in UTC
    start_date_utc = start_date.astimezone(pytz.UTC)
    end_date_utc = end_date.astimezone(pytz.UTC)
    
    # Format dates as RFC3339 timestamps
    time_min = start_date_utc.isoformat().replace('+00:00', 'Z')
    time_max = end_date_utc.isoformat().replace('+00:00', 'Z')
    
    events_result = service.events().list(calendarId=calendar_id, 
                                          timeMin=time_min,
                                          timeMax=time_max,
                                          singleEvents=True,
                                          orderBy='startTime').execute()
    events = events_result.get('items', [])

    for event in events:
        service.events().delete(calendarId=calendar_id, eventId=event['id']).execute()
        print(f"Deleted event: {event.get('summary', 'No Title')}")

def import_ics_to_google_calendar(service, ics_file, calendar_id):
    with open(ics_file, 'rb') as f:
        cal = Calendar.from_ical(f.read())
    
    for component in cal.walk():
        if component.name == "VEVENT":
            dtstart = component.get('dtstart')
            dtend = component.get('dtend')
            
            # Skip events without start time
            if not dtstart:
                continue
                
            start = dtstart.dt
            
            # If no end time, use start time + 1 hour as default
            if dtend:
                end = dtend.dt
            else:
                end = start + timedelta(hours=1) if isinstance(start, datetime) else start
            
            # Convert to datetime if it's a date
            if isinstance(start, date) and not isinstance(start, datetime):
                start = datetime.combine(start, datetime.min.time())
            if isinstance(end, date) and not isinstance(end, datetime):
                end = datetime.combine(end, datetime.min.time())
            
            # Ensure timezone information
            paris_tz = pytz.timezone('Europe/Paris')
            if start.tzinfo is None:
                start = paris_tz.localize(start)
            if end.tzinfo is None:
                end = paris_tz.localize(end)
            
            event = {
                'summary': str(component.get('summary', 'No Title')),
                'location': str(component.get('location', '')),
                'description': str(component.get('description', '')),
                'start': {
                    'dateTime': start.isoformat(),
                    'timeZone': 'Europe/Paris',
                },
                'end': {
                    'dateTime': end.isoformat(),
                    'timeZone': 'Europe/Paris',
                },
            }
            created_event = service.events().insert(calendarId=calendar_id, body=event).execute()
            print(f"Created event: {created_event['summary']}")

def main(ics_files):
    service = get_google_calendar_service()

    for calendar_name, ics_file in ics_files:
        # Skip the main calendar
        if "calendar_Main_" in ics_file:
            print(f"Skipping main calendar file: {ics_file}")
            continue
        # Extract the module number from the calendar name
        module = calendar_name.split()[0] if calendar_name != "Main" else "Other"
        
        # Get the corresponding calendar ID
        calendar_id = CALENDAR_IDS.get(module)
        
        if not calendar_id:
            print(f"Warning: No predefined calendar ID found for {calendar_name}. Skipping.")
            continue

        # Extract start and end dates from the filename
        file_name = os.path.basename(ics_file)
        date_range = file_name.split('_')[-2:]
        start_date = datetime.strptime(date_range[0], "%Y-%m-%d")
        end_date = datetime.strptime(date_range[1].split('.')[0], "%Y-%m-%d")
        
        print(f"Clearing existing events for {calendar_name}...")
        clear_calendar_range(service, calendar_id, start_date, end_date)
        
        print(f"Importing events for {calendar_name}...")
        import_ics_to_google_calendar(service, ics_file, calendar_id)

    print("All calendars have been imported to Google Calendar.")

if __name__ == "__main__":
    # This allows the script to be run independently for testing
    from oniris_calendar import main as oniris_main
    ics_files = oniris_main()
    if ics_files:
        main(ics_files)
    else:
        print("No ICS files were generated or an error occurred.")