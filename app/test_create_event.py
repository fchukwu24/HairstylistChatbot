import os
from datetime import datetime, timedelta

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


SCOPES = ["https://www.googleapis.com/auth/calendar"]

BASE_DIR = os.path.dirname(__file__)
TOKEN_FILE = os.path.join(BASE_DIR, "token.json")


def get_calendar_service():
    creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    return build("calendar", "v3", credentials=creds)


def main():
    service = get_calendar_service()

    # Change this if you want to use a different calendar from the list.
    calendar_id = os.getenv("GOOGLE_CALENDAR_ID", "primary")
    print(calendar_id)
    start_time = datetime.now() + timedelta(days=1)
    start_time = start_time.replace(hour=14, minute=30, second=0, microsecond=0)

    end_time = start_time + timedelta(minutes=60)

    event = {
        "summary": "TEST Haircut appointment with Jordan",
        "description": "Test event created by Haircare Assistant.",
        "start": {
            "dateTime": start_time.isoformat(),
            "timeZone": "America/Detroit",
        },
        "end": {
            "dateTime": end_time.isoformat(),
            "timeZone": "America/Detroit",
        },
    }

    created_event = service.events().insert(
        calendarId=calendar_id,
        body=event,
        sendUpdates="all",
    ).execute()

    print("Event created!")
    print("Title:", created_event.get("summary"))
    print("Start:", created_event.get("start"))
    print("Link:", created_event.get("htmlLink"))


if __name__ == "__main__":
    main()