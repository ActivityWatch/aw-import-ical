import sys
from datetime import datetime, date, time

from icalendar import Calendar

from aw_core.models import Event
from aw_client import ActivityWatchClient


def coerce2datetime(d):
    if isinstance(d, datetime):
        return d
    elif isinstance(d, date):
        return datetime.combine(d, time())
    else:
        raise TypeError


def load_events(filepath):
    with open(filepath) as f:
        gcal = Calendar.from_ical(f.read())

    events = []
    for component in gcal.walk():
        if component.name == "VEVENT":
            # TODO: Test that timezones work properly
            # TODO: Handle recurrence rules
            title = component.decoded('summary').decode("utf8")

            start = coerce2datetime(component.decoded('dtstart'))
            end = coerce2datetime(component.decoded('dtend'))
            duration = end - start

            attendees = [str(attendee) for attendee in (component.get('attendee') or [])]

            e = Event(timestamp=start, duration=duration, data={"title": title, "attendees": attendees})
            events.append(e)

            # print(title)
            # print(start, duration)
            # if attendees:
            #     for attendee in attendees:
            #         print(attendee)
            # print(e)
            # print(component)
            # print(80 * "-")
    return events


if __name__ == "__main__":
    filename = sys.argv.pop()
    events = load_events(filename)
    print(f"Loaded {len(events)} events")
    aw = ActivityWatchClient(testing=True)

    bucket_name = 'ical-import'

    if bucket_name in aw.get_buckets():
        aw.delete_bucket(bucket_name)

    aw.create_bucket(bucket_name, 'calendar')
    aw.insert_events(bucket_name, events)


"""
Basic query:

events = query_bucket(find_bucket('ical-import'));
RETURN = filter_keyvals_regex(events, 'title', '\<\>'));
"""
