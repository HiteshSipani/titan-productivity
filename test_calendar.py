from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
import pickle
from datetime import datetime

with open('token.pickle', 'rb') as f:
    creds = pickle.load(f)

if creds.expired and creds.refresh_token:
    creds.refresh(Request())

service = build('calendar', 'v3', credentials=creds)

now = datetime.utcnow()
start = now.replace(hour=0, minute=0, second=0).isoformat() + 'Z'
end = now.replace(hour=23, minute=59, second=59).isoformat() + 'Z'

events_result = service.events().list(
    calendarId='primary',
    timeMin=start,
    timeMax=end,
    singleEvents=True,
    orderBy='startTime'
).execute()

events = events_result.get('items', [])
print(f"Found {len(events)} events today:")
for e in events:
    print(f"  - {e.get('summary', 'Untitled')} at {e['start'].get('dateTime', e['start'].get('date'))}")
