from googleapiclient.discovery import build
from google.auth.transport.requests import Request
import pickle
from datetime import datetime, timedelta

with open('token.pickle', 'rb') as f:
    creds = pickle.load(f)

if creds.expired and creds.refresh_token:
    creds.refresh(Request())

service = build('calendar', 'v3', credentials=creds)

now = datetime.now()
start = now.replace(hour=15, minute=0, second=0).isoformat()
end = now.replace(hour=16, minute=0, second=0).isoformat()

event = {
    'summary': '[FOCUS] Hackathon Submission',
    'description': 'Created by Titan Productivity Agent',
    'start': {'dateTime': start, 'timeZone': 'Asia/Kolkata'},
    'end': {'dateTime': end, 'timeZone': 'Asia/Kolkata'},
}

created = service.events().insert(calendarId='primary', body=event).execute()
print(f"Event created: {created.get('summary')}")
print(f"Link: {created.get('htmlLink')}")
