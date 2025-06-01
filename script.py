import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import uuid
import pytz
import re
import urllib.parse
import time
import json
import html
from dotenv import load_dotenv

load_dotenv()

domain = os.getenv("DOMAIN")

def login(username, password):
    login_url = f"https://{domain}/LdapLogin"
    logon_url = f"https://{domain}/LdapLogin/Logon"
    session = requests.Session()

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:130.0) Gecko/20100101 Firefox/130.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Content-Type": "application/x-www-form-urlencoded",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1"
    }

    response = session.get(login_url, headers=headers)
    
    if response.status_code != 200:
        raise Exception(f"Failed to load login page. Status code: {response.status_code}")

    soup = BeautifulSoup(response.text, 'html.parser')
    token = soup.find('input', {'name': '__RequestVerificationToken'})
    if token is None:
        raise Exception("Anti-forgery token not found on login page")
    
    token = token['value']
    print(f"Anti-forgery token found: {token[:10]}...")

    login_data = {
        'Name': username,
        'Password': password,
        '__RequestVerificationToken': token,
        'RememberMe': 'false'
    }

    encoded_data = urllib.parse.urlencode(login_data)

    response = session.post(logon_url, data=encoded_data, headers=headers, allow_redirects=True)

    if "LdapLogin" in response.url:
        soup = BeautifulSoup(response.text, 'html.parser')
        error_message = soup.find('span', {'data-valmsg-for': 'WrongCredentials'})
        if error_message:
            print(f"Error message found: {error_message.text}")
        raise Exception("Login failed. Please check your credentials.")

    if "CalendarViewType=Unknown" in response.url:
        print("Login successful! Redirected to calendar page.")
        
        # Navigate to the specific calendar view
        calendar_url = f"https://{domain}/cal?vt=month&dt={datetime.now().strftime('%Y-%m-%d')}&et=student&fid0={urllib.parse.quote(username)}"
        response = session.get(calendar_url, headers=headers)
        
        if response.status_code != 200:
            raise Exception(f"Failed to load calendar page. Status code: {response.status_code}")
        
        print("Successfully loaded calendar page.")
    else:
        print(f"Unexpected redirect to {response.url}")
        raise Exception("Login process resulted in an unexpected redirect")

    federation_id = extract_federation_id(response)
    
    if federation_id:
        print(f"Successfully extracted federation ID: {federation_id}")
    else:
        print("Unable to automatically extract federation ID. You may need to provide it manually.")

    return session, federation_id

def extract_federation_id(response):
    # Method 1: Try to extract from URL
    match = re.search(r'fid0=([^&]+)', response.url)
    if match:
        return urllib.parse.unquote(match.group(1))

    # Method 2: Try to extract from page content
    soup = BeautifulSoup(response.text, 'html.parser')
    logout_link = soup.find('a', class_='logInOrOut')
    if logout_link:
        small_span = logout_link.find('span', class_='small')
        if small_span:
            # Extract the text after the hyphen
            federation_id = small_span.text.strip().split('-')[-1].strip()
            if federation_id:
                return federation_id

    # Method 3: Try to extract from cookies
    for cookie in response.cookies:
        if 'FederationId' in cookie.name:
            return cookie.value

    return None

def get_data(session, start_date, end_date, federation_id):
    if not federation_id:
        raise ValueError("Federation ID cannot be empty")

    url = f"https://{domain}/Home/GetCalendarData"
    referrer = f"https://{domain}/cal?vt=month&dt={start_date.strftime('%Y-%m-%d')}&et=student&fid0={urllib.parse.quote(federation_id)}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:130.0) Gecko/20100101 Firefox/130.0",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "en-US,en;q=0.5",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Sec-GPC": "1",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "Referer": referrer
    }
    
    data = {
        "start": start_date.strftime("%Y-%m-%d"),
        "end": end_date.strftime("%Y-%m-%d"),
        "resType": "104",
        "calView": "month",
        "federationIds[]": federation_id,
        "colourScheme": "6"
    }
    
    """ print(f"\n--- Request Details ---")
    print(f"URL: {url}")
    print(f"Headers:")
    for key, value in headers.items():
        print(f"  {key}: {value}")
    print(f"Data:")
    for key, value in data.items():
        print(f"  {key}: {value}")
    
    print("\n--- Cookies ---")
    for cookie in session.cookies:
        print(f"  {cookie.name}: {cookie.value}") """
    
    try:
        response = session.post(url, headers=headers, data=data)
        """ print("\n--- Response Details ---")
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers:")
        for key, value in response.headers.items():
            print(f"  {key}: {value}")
        
        print("\n--- Response Content ---")
        print(response.text[:1000])  # Print first 1000 characters of the response """
        
        if response.text:
            try:
                json_data = response.json()
                """ print("\n--- Parsed JSON Data ---")
                print(f"Number of events: {len(json_data)}")
                if json_data:
                    print("First event:")
                    print(json.dumps(json_data[0], indent=2))
                else:
                    print("JSON data is empty") """
                return json_data
            except json.JSONDecodeError as e:
                print(f"Failed to parse JSON: {e}")
                return None
        else:
            print("Response content is empty")
            return None
    
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        raise


def get_category_color(category):
    colors = {
        "TD": "#ff8080",
        "CM": "#8080ff",
        "e-learning": "#80ff80",
        "Journée Thématique": "#ffff80"
    }
    return colors.get(category, "#ffc4c4")

def parse_event(event):
    description_lines = event['description'].split('<br />')
    
    title = f"{event['eventCategory']} - {event['modules'][0]}" if event['modules'] else f"{event['eventCategory']} - Other"
    description = description_lines[0].strip()
    
    locations = []
    teachers = []
    class_groups = []
    
    for line in description_lines[1:]:
        line = html.unescape(line.strip())
        
        if any(keyword in line.lower() for keyword in ["porte", "amphi", "espace modulaire", "salle"]):
            locations.append(line)
        elif '[' in line and ']' in line and any(class_keyword in line.lower() for class_keyword in ["vet", "classe", "group"]):
            class_groups.append(line)
        elif line and not any(keyword in line.lower() for keyword in ["td", "cm", "e-learning", "journée thématique", "porte", "amphi", "conférences", "congrès", "[", "]", "03", "auto-évaluation en ligne", "travail", "tp", "contrôle", "forum"]):
            teachers.append(line)
    
    return {
        "title": title,
        "description": description,
        "locations": locations,
        "teachers": teachers,
        "class_groups": class_groups,
        "category": event['eventCategory'],
        "module": event['modules'][0] if event['modules'] else "Other"
    }

def get_module_color(module):
    color_scheme = {
        "031": "11",  # Red
        "032": "10",  # Green
        "033": "9",   # Blue
        "034": "5",   # Yellow
        "035": "4",   # Purple
        "036": "7",   # Cyan
        "037": "6",   # Orange
        "038": "3",   # Purple
        "039": "2",   # Green
        "041": "1",    # Red
        "042": "12",  # Blue
        "043": "13",  # Green
        "044": "14",  # Yellow
        "045": "15",  # Purple
        "046": "16",  # Cyan
        "047": "17",  # Orange
        "048": "18",  # Purple
        "049": "19",  # Green
        "Other": "8"  # Gray
    }
    
    module_number = module.split()[0] if module != "Other" else "Other"
    return color_scheme.get(module_number, color_scheme["Other"])

def get_module_calendars(data):
    calendars = {}
    for event in data:
        if event['eventCategory'] in ["CONGES", "FERIE", "PONT", "Stage", "Férié"] or event['eventCategory'] is None:
            continue
        
        details = parse_event(event)
        module = details['module'].split()[0] if details['module'] != "Other" else "Other"
        
        if not module or module == "Other":
                module = "Other"

        if module not in calendars:
            calendars[module] = []
        
        calendars[module].append((event, details))
    
    if "Other" not in calendars:
        calendars["Other"] = []

    return calendars


def generate_ical(events, calendar_name):
    ical = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:-//Oniris Nantes//CELCAT {calendar_name}//FR",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:CELCAT-EDT {calendar_name}",
        "X-WR-TIMEZONE:Europe/Paris"
    ]

    now = datetime.now(pytz.utc).strftime("%Y%m%dT%H%M%SZ")

    def clean_and_escape(text):
        # First, decode HTML entities
        decoded = html.unescape(text)
        # Then, escape special characters for iCalendar
        return decoded.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")

    for event, details in events:
        description = f"{details['description']}\n"
        if details['locations']:
            description += f"Salle(s): {', '.join(details['locations'])}\n"
        if details['teachers']:
            description += f"Professeur(e)(s): {', '.join(details['teachers'])}\n"
        if details['class_groups']:
            description += f"Classe(s)/Groupe(s): {', '.join(details['class_groups'])}"
        
        # Clean and escape all text fields
        cleaned_description = clean_and_escape(description)
        cleaned_title = clean_and_escape(details['title'])
        cleaned_category = clean_and_escape(details['category'])

        ical.extend([
            "BEGIN:VEVENT",
            f"UID:{event['id']}",
            f"DTSTAMP:{now}",
            f"DTSTART:{event['start'].replace('-', '').replace(':', '')}",
            f"DTEND:{event['end'].replace('-', '').replace(':', '')}",  # Corrected this line
            f"SUMMARY:{cleaned_title}",
            f"DESCRIPTION:{cleaned_description}",
            f"CATEGORIES:{cleaned_category}",
        ])

        ical.append("END:VEVENT")

    ical.append("END:VCALENDAR")
    return "\r\n".join(ical)


def data_to_ical(data):
    module_calendars = get_module_calendars(data)
    ical_calendars = {}

    # Generate main calendar
    all_events = [item for sublist in module_calendars.values() for item in sublist]
    ical_calendars["Main"] = generate_ical(all_events, "Main")
    # Generate individual module calendars
    for module, events in module_calendars.items():
        ical_calendars[module] = generate_ical(events, module)

    return ical_calendars

def get_month_range(year, month):
    start_date = datetime(year, month, 1)
    if month == 12:
        end_date = datetime(year + 1, 1, 1)
    else:
        end_date = datetime(year, month + 1, 1)
    return start_date, end_date - timedelta(days=1)

def main():
    username = input("Enter your username: ")
    password = input("Enter your password: ")

    try:
        session, federation_id = login(username, password)
        print("Login successful!")

        if not federation_id:
            federation_id = input("Enter your Federation ID manually (generally it's Lastname Firstname): ")

        time.sleep(1)

        # Get current year and month
        current_date = datetime.now()
        current_year = current_date.year
        current_month = current_date.month

        # Ask user for year and month
        year = int(input(f"Enter year (default: {current_year}): ") or current_year)
        month = int(input(f"Enter month (1-12, default: {current_month}): ") or current_month)

        # Validate month input
        if month < 1 or month > 12:
            print("Invalid month. Using current month.")
            month = current_month

        start_date, end_date = get_month_range(year, month)

        print(f"Fetching calendar data from {start_date.date()} to {end_date.date()}...")
        data = get_data(session, start_date, end_date, federation_id)
        print("Successfully retrieved and parsed JSON data.")
        print(f"Number of events: {len(data)}")
        
        if data is None:
            print("Failed to retrieve or parse calendar data.")
            return []
        elif not data:
            print("No events found in the specified date range.")
            return []
        else:
            print(f"Successfully retrieved {len(data)} events.")

        ical_calendars = data_to_ical(data)

        import_all = input("Do you want to import all sub-calendars? (yes/no, default: yes): ").lower() != 'no'

        # Create a directory for the calendar files
        import os
        directory = f"calendar_export_{start_date.date()}_{end_date.date()}"
        os.makedirs(directory, exist_ok=True)

        generated_files = []
        if import_all:
            for calendar_name, ical_data in ical_calendars.items():
                filename = f"{directory}/calendar_{calendar_name}_{start_date.date()}_{end_date.date()}.ics"
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(ical_data)
                print(f"Calendar data for {calendar_name} has been exported to {filename}")
                generated_files.append((calendar_name, filename))
        else:
            print("Available sub-calendars:")
            for i, calendar_name in enumerate(ical_calendars.keys(), 1):
                print(f"{i}. {calendar_name}")
            
            while True:
                choice = input("Enter the number of the sub-calendar you want to import: ")
                try:
                    index = int(choice) - 1
                    if 0 <= index < len(ical_calendars):
                        calendar_name = list(ical_calendars.keys())[index]
                        ical_data = ical_calendars[calendar_name]
                        filename = f"{directory}/calendar_{calendar_name}_{start_date.date()}_{end_date.date()}.ics"
                        with open(filename, "w", encoding="utf-8") as f:
                            f.write(ical_data)
                        print(f"Calendar data for {calendar_name} has been exported to {filename}")
                        generated_files.append((calendar_name, filename))
                        break
                    else:
                        print("Invalid choice. Please try again.")
                except ValueError:
                    print("Invalid input. Please enter a number.")
        
        print(f"\nAll calendar files have been exported to the '{directory}' directory.")
        return generated_files

    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return []

if __name__ == "__main__":
    main()
