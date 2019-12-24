from __future__ import print_function
from datetime import datetime
import pickle
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from aw_core.models import Event
from aw_client import ActivityWatchClient


# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
calendarId = 'primary'

def get_token():
    try:
        with open('token.txt','r') as f:
            token = f.readline()
    except FileNotFoundError:
        token = None
    return token

def store_token(token):
    with open('token.txt','w') as f:
        f.write(token)

def calendar_list():
    service = build('calendar', 'v3', credentials=get_credentials())
    calendar_list = service.calendarList().list().execute()
    return calendar_list

def get_credentials():
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    return creds

def capture_events():
    events_list = []
    syncToken = get_token()
    service = build('calendar', 'v3', credentials=get_credentials())
    # Call the Calendar API
    events_result = service.events().list(calendarId=calendarId,
                                        syncToken=syncToken).execute()
    events = events_result.get('items', [])
    events_list.append(events)
    # We have captured all of the events since the last token, only when the response
    # returns the nextSyncToken
    nextSyncToken = events_result.get('nextSyncToken',None)
    while nextSyncToken is None:
        nextPageToken = events_result.get('nextPageToken',None)
        events_result = service.events().list(calendarId=calendarId,
            syncToken=syncToken, pageToken=nextPageToken).execute()
        events = events_result.get('items', [])
        events_list.append(events)
        nextSyncToken = events_result.get('nextSyncToken',None)
    store_token(nextSyncToken)
    return events_list

def interpret_events(list_of_events):
    events_to_insert = []
    cancelled_event_ids = []
    for event_list in list_of_events:
        for event in event_list:
            #TODO figure out timezone
            print(event)
            if event['status'] in ['confirmed', 'tentative']:
                event_id = event['id']
                status = 1
                label = event['summary']
                datastr = {'event_id':event_id, 'label':label, 'status':status}
                if ('recurrence' in event.keys()): datastr['recurrence'] = str(event['recurrence'])
                if ('recurringEventId' in event.keys()): datastr['recurringEventId'] = event['recurringEventId'] 
                if 'originalStartTime' in event.keys():
                    originalStartTime = event['originalStartTime'].get('dateTime', event['originalStartTime'].get('date'))
                    datastr['originalStartTime'] = originalStartTime
                    originalTimeZone = event['originalStartTime'].get('timeZone')
                if event['start'].get('dateTime') != None:
                    start = event['start'].get('dateTime')
                    start_time = datetime.strptime(start, '%Y-%m-%dT%H:%M:%S%z')
                else:
                    start = event['start'].get('date')
                    start_time = datetime.strptime(start, '%Y-%m-%d')
                start_timezone = event['start'].get('timeZone', None)
                if event['end'].get('dateTime') != None:
                    end = event['end'].get('dateTime')
                    end_time = datetime.strptime(end, '%Y-%m-%dT%H:%M:%S%z')
                else:
                    end = event['end'].get('date')
                    end_time = datetime.strptime(end, '%Y-%m-%d')
                end_timezone = event['end'].get('timeZone', None)

                duration = end_time - start_time
                event = Event(timestamp=start_time, duration=duration, data=datastr)
                events_to_insert.append(event)
                
            else: # event is cancelled
                event_id = event['id']
                status = 0
                # check if the event is part of an uncancelled recurring event.
                # If it is, that means that it needs to be stored as this instance
                # should no longer be shown to the user
                # otherwise this event needs to be deleted from the database.
                
                # event should be deleted from database
                if 'recurringEventId' not in event.keys() and 'originalStartTime' not in event.keys():
                    cancelled_event_ids.append(event_id)
                else: # it's part of a still existing recurring event
                    recurringEventId = event['recurringEventId'] if 'recurringEventId' in event.keys() else ''
                    if event['originalStartTime'].get('dateTime') != None:
                        originalStartTime = event['originalStartTime'].get('dateTime')
                        print("originalStartTime", originalStartTime)
                    else:
                        originalStartTime = datetime.strptime(originalStartTime, '%Y-%m-%dT%H:%M:%S%z')
                        originalStartTime = event['originalStartTime'].get('date')
                        originalStartTime = datetime.strptime(originalStartTime, '%Y-%m-%d')
                        print("originalStartTime", originalStartTime)

                    originalTimeZone = event['originalStartTime'].get('timeZone')
                    event = Event(timestamp = originalStartTime, duration = 0,
                    data = {'event_id': event_id, 'status':status,'recurringEventId':recurringEventId,'originalStartTime':str(originalStartTime)})      
                    events_to_insert.append(event)

    return events_to_insert, cancelled_event_ids

if __name__ == "__main__":
    events_to_insert, cancelled_event_ids = interpret_events(capture_events())
    print(events_to_insert)

    aw = ActivityWatchClient(testing=True)

    bucket_name = 'aw-calendar-import'

    if bucket_name not in aw.get_buckets():
        aw.create_bucket(bucket_name, 'calendar')
    
    aw.insert_events(bucket_name, events_to_insert)
    for id_to_del in cancelled_event_ids:
        # aw.delete_calendar_event(bucket_name, id_to_del)
        pass