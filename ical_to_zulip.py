import os
import requests
from icalendar import Calendar
import datetime as dt
from datetime import datetime, timedelta
from zulip import Client
from dotenv import load_dotenv


IMPORTANT_COMPONENTS = ["SUMMARY", "DTSTART", "DTEND", "LOCATION", "DESCRIPTION"]

# Load environment variables
load_dotenv()

# Configuration from .env file
ICAL_URL = os.getenv("ICAL_URL")
ZULIP_EMAIL = os.getenv("ZULIP_BOT_EMAIL")
ZULIP_API_KEY = os.getenv("ZULIP_API_KEY")
ZULIP_SITE = os.getenv("ZULIP_SITE")
CHANNEL = os.getenv("ZULIP_CHANNEL")
# Number of days to check for updated events, default is 1 due to the bot running daily
TIMEDELTA_DAYS = 1


class ICalToZulipBot:
    def __init__(self):
        self.client = Client(email=ZULIP_EMAIL, api_key=ZULIP_API_KEY, site=ZULIP_SITE)

    def component_to_event(self, component):
        # TODO: Handle start and ends are dates
        event = {
            "summary": component.get("SUMMARY"),
            "start": component.get("DTSTART").dt.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "end": component.get("DTEND").dt.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "location": component.get("LOCATION"),
            "description": component.get("DESCRIPTION"),
            "created": component.get("CREATED"),
            "last_modified": component.get("LAST-MODIFIED"),
        }
        return event

    def event_to_message(self, event):
        message = {
            "type": "stream",
            "to": CHANNEL,
            "subject": event["summary"],
        }
        if event["description"] is None:
            event["description"] = ""

        content = f"""Summary: {event['description']}
        Location: {event['location']} 
        Start:  <time:{event['start'][:-2]+':'+ event['start'][-2:]}>
        End: <time:{event['end'][:-2]+':'+ event['end'][-2:]}>
        """
        message["content"] = content
        return message

    def daily_events_message(self, events):
        message = {
            "type": "stream",
            "to": CHANNEL,
            "subject": "Daily Events",
        }
        message["content"] = f"""/poll today's events:"""
        for event in events:
            message["content"] += f"\n{event['summary']}"
        return message

    def handle_message(self, message=None):

        events = self.fetch_calendar_events()
        events = sorted(events, key=lambda x: x["start"])

        NOW = datetime.now(dt.UTC)

        UPDATED_EVENTS_FILTER = lambda x: x.get("last_modified").dt > (
            NOW - timedelta(days=TIMEDELTA_DAYS)
        ) or x.get("created").dt > (NOW - timedelta(days=TIMEDELTA_DAYS))

        updated_events = filter(UPDATED_EVENTS_FILTER, events)

        for event in updated_events:
            response = self.event_to_message(event)
            if response:
                self.send_message(response)

        EVENTS_TODAY_FILTER = (
            lambda x: dt.datetime.strptime(x["start"], "%Y-%m-%dT%H:%M:%S%z").date()
            == NOW.date()
        )
        events_today = list(filter(EVENTS_TODAY_FILTER, events))

        if len(events_today) > 0:
            events_today = sorted(events_today, key=lambda x: x["start"])
            daily_event_poll = self.daily_events_message(events_today)
            self.send_message(daily_event_poll)
        return

    def fetch_calendar_events(self):
        response = requests.get(ICAL_URL)
        cal = Calendar.from_ical(response.text)

        events = []

        for component in cal.walk():
            if component.name == "VEVENT":
                event = self.component_to_event(component)
                events.append(event)

        return events

    def send_message(self, message):
        self.client.send_message(message)


if __name__ == "__main__":
    bot = ICalToZulipBot()
    bot.handle_message()
