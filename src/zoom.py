import os
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

ZOOM_ACCOUNT_ID = os.getenv("ZOOM_ACCOUNT_ID")
ZOOM_CLIENT_ID = os.getenv("ZOOM_CLIENT_ID")
ZOOM_CLIENT_SECRET = os.getenv("ZOOM_CLIENT_SECRET")


def get_access_token():
    """Obtain an access token from Zoom using Server-to-Server OAuth."""
    url = "https://zoom.us/oauth/token"
    data = {
        "grant_type": "account_credentials",
        "account_id": ZOOM_ACCOUNT_ID
    }
    response = requests.post(url, auth=(ZOOM_CLIENT_ID, ZOOM_CLIENT_SECRET), data=data)
    response.raise_for_status()
    return response.json()["access_token"]



def create_meeting(date: str, time: str, purpose: str) -> str:
    """Create a Zoom meeting for the given date, time, and purpose, returning the join URL."""
    access_token = get_access_token()
    dt = datetime.strptime(f"{date} {time}", "%d/%m/%Y %H:%M")
    start_time = dt.strftime("%Y-%m-%dT%H:%M:00Z")
    url = "https://api.zoom.us/v2/users/me/meetings"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    data = {
        "topic": f"Appointment: {purpose}",
        "type": 2,  
        "start_time": start_time,
        "duration": 30, 
        "timezone": "UTC"
    }
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    meeting = response.json()
    return meeting["join_url"]