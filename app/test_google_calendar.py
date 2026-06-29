import os

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


SCOPES = ["https://www.googleapis.com/auth/calendar"]

BASE_DIR = os.path.dirname(__file__)
CREDENTIALS_FILE = os.path.join(BASE_DIR, "credentials.json")
TOKEN_FILE = os.path.join(BASE_DIR, "token.json")


def get_calendar_service():
    creds = None

    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(
            CREDENTIALS_FILE,
            SCOPES,
        )

        creds = flow.run_local_server(host="localhost", bind_addr="0.0.0.0", port=8080, open_browser=False,)

        with open(TOKEN_FILE, "w", encoding="utf-8") as token:
            token.write(creds.to_json())

    return build("calendar", "v3", credentials=creds)


def main():
    service = get_calendar_service()

    calendar_list = service.calendarList().list().execute()

    print("Connected to Google Calendar!")
    print("Calendars:")

    for calendar in calendar_list.get("items", []):
        print("-", calendar.get("summary"), "|", calendar.get("id"))


if __name__ == "__main__":
    main()