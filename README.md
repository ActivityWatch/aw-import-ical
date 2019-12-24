aw-import-ical
==============

An importer which continuously synchronizes Google Calendar with ActivityWatch.

## Setup

* You have to enable Google Calendar API in the API Console. Once you do that, download `credentials.json` [(Console Website)](https://console.developers.google.com/) and place it in the aw-import-ical folder.

## Usage

Requires Python 3.6+ and pipenv.

```
pipenv install
pipenv run python3 synchronize.py
```
