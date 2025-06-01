from script import main as oniris_main
from import_google import main as google_import

def main():
    print("Fetching Oniris calendar data and generating ICS files...")
    ics_files = oniris_main()
    
    if ics_files:
        print("\nICS files generated successfully.")
        import_to_google = input("Do you want to import these calendars to Google Calendar? (y/n): ").lower()
        if import_to_google == 'y':
            print("\nImporting to Google Calendar...")
            google_import(ics_files)
        else:
            print("Skipping Google Calendar import.")
    else:
        print("No ICS files were generated or an error occurred.")

if __name__ == "__main__":
    main()