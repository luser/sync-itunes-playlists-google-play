This repository contains a Python script that can one-way sync playlists
from an iTunes library to Google Play Music. The Google Music Uploader
claims to do this but it does a terrible job in practice.

Usage
=====

1) Create a virtualenv and install requirements:
```
virtualenv venv
. venv/bin/activate
pip install -r requirements.txt
```
2) Run sync.py, passing it the path to your iTunes library and Music Manager database, and optionally the names of playlists to sync:
```
python sync.py "/path/to/iTunes Music Library.xml" "/path/to/ServerDatabase.db" [playlists]
```

Any copyright is dedicated to the Public Domain.
http://creativecommons.org/publicdomain/zero/1.0/
