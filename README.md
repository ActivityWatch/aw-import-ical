aw-import-ical
==============

An `.ical` importer and Google Calendar synchronizer for ActivityWatch.

## Setup

* To use the Google Calendar synchronizer, you have to enable Google Calendar API in the API Console. Once you do that, download `credentials.json` [(Console Website)](https://console.developers.google.com/) and place it in the aw-import-ical folder.

## Usage

Requires Python 3.7+ and pipenv.

```sh
pipenv install

# To run importer
pipenv run python3 main.py <filepath of ical file>

# To run synchronizer
pipenv run python3 synchronize.py
```
