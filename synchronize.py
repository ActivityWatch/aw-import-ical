from __future__ import print_function
import os
from datetime import datetime, timedelta, timezone
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
            date, token  = f.readline().split(' ')
    except FileNotFoundError:
        token = None
        date = None
    return token, date

def store_token(token):
    with open('token.txt','w') as f:
        f.write(str(datetime.now().date()) + " " + token)

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
    syncToken, date_stored = get_token()
    time_max = datetime.now(timezone.utc) + timedelta(days=2)
    time_max = datetime.strftime(time_max, '%Y-%m-%dT%H:%M:%S%z')
    service = build('calendar', 'v3', credentials=get_credentials())
    # Call the Calendar API
    # if token date does not exist(meaning no syncing previously) or not the same as today, automatically do a new backup.
    # This is necessary because we're passing the timeMax parameter when doing a full sync so that we only store events in the 
    # database for a max of 2 days from now. Therefore do a full sync every new day to get the events after 2 days from now.
    if (date_stored is None or date_stored != str(datetime.now().date())):
        print("token date is None or not today")
        events_result = service.events().list(calendarId=calendarId, singleEvents=True, timeMax=str(time_max)).execute()
        events = events_result.get('items', [])
    else: # dates are the same, so first try an incremental sync(using synctoken) to check if there are any new changes
        events_result = service.events().list(calendarId=calendarId, syncToken=syncToken, singleEvents=True).execute()
        events = events_result.get('items', [])
        if(len(events) == 0):
            print("no new events")
            return events_list
        # there is at least one new event, so have to do a full sync
        else:
            print("found new events")
            events_result = service.events().list(calendarId=calendarId, singleEvents=True, timeMax=str(time_max)).execute()
            events = events_result.get('items', [])
    events_list.extend(events)
    # We have captured all of the events since the last token, only when the response
    # returns the nextSyncToken
    nextSyncToken = events_result.get('nextSyncToken',None)
    while nextSyncToken is None:
        nextPageToken = events_result.get('nextPageToken',None)
        events_result = service.events().list(calendarId=calendarId, singleEvents=True, pageToken=nextPageToken, timeMax=str(time_max)).execute()
        events = events_result.get('items', [])
        events_list.extend(events)
        nextSyncToken = events_result.get('nextSyncToken',None)
    store_token(nextSyncToken)
    return events_list

def interpret_events(list_of_events):
    events_to_insert = []
    for event in list_of_events:
        label = event['summary']
        datastr = {'label':label}
        if event['start'].get('dateTime') != None:
            start = event['start'].get('dateTime')
            start_time = datetime.strptime(start, '%Y-%m-%dT%H:%M:%S%z')
        else:
            start = event['start'].get('date')
            start_time = datetime.strptime(start, '%Y-%m-%d')
        if event['end'].get('dateTime') != None:
            end = event['end'].get('dateTime')
            end_time = datetime.strptime(end, '%Y-%m-%dT%H:%M:%S%z')
        else:
            end = event['end'].get('date')
            end_time = datetime.strptime(end, '%Y-%m-%d')

        duration = end_time - start_time
        event = Event(timestamp=start_time.isoformat(), duration=duration, data=datastr)
        events_to_insert.append(event)

    return events_to_insert


captured_events = capture_events()


events_to_insert = interpret_events(captured_events)

if(events_to_insert):
    try:
        aw = ActivityWatchClient(testing=True)
        bucket_name = 'aw-calendar-import'
        try:
            aw.delete_bucket(bucket_name)
        except:
            print("Bucket doesn't exist") 
        aw.create_bucket(bucket_name, 'calendar')
        aw.insert_events(bucket_name, events_to_insert)
    except:
        print("something went wrong")
        if os.path.exists("token.txt"):
            os.remove("token.txt")
        exit
