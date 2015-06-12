# Any copyright is dedicated to the Public Domain.
# http://creativecommons.org/publicdomain/zero/1.0/

from __future__ import print_function

import argparse
import difflib
import os
import pyItunes
import sqlite3
import sys

from gmusicapi import Mobileclient
from collections import defaultdict

# This is terrible.
import requests.packages.urllib3
requests.packages.urllib3.disable_warnings()

verbose = False

def log(*args, **kwargs):
    if verbose:
        print(*args, **kwargs)

def get_track_ids(db, tracks):
    '''
    Return a list of server ids for each track in tracks.
    '''
    ids = {}
    for row in db.execute("select replace(FileHandle, '\\', '/') as filename, ServerId from XFILES where filename in (%s)" % ','.join('?' * len(tracks)), [t.location for t in tracks]):
        ids[row[0]] = row[1]
    return [ids[t.location] for t in tracks]

def index(l, f):
   return next((i for i in xrange(len(l)) if f(l[i])), None)


def create_playlist(api, db, playlist):
    track_ids = get_track_ids(db, playlist.tracks)
    log('Playlist "%s": %d songs' % (playlist.name, len(playlist.tracks)))
    playlist_id = api.create_playlist(playlist.name)
    added_songs = api.add_songs_to_playlist(playlist_id, track_ids)
    log('Added %d songs' % len(added_songs))

def sync_playlist(api, db, playlist, google_playlists):
    if playlist.name not in google_playlists:
        # This is the easy case
        create_playlist(api, db, playlist)
        return
    google_playlist = google_playlists[playlist.name]
    playlist_id = google_playlist['id']
    # First, remove tracks from the list.
    track_ids = get_track_ids(db, playlist.tracks)
    existing_track_ids = [t['trackId'] for t in google_playlist['tracks']]
    log('Playlist "%s": %d songs in iTunes, %d in Google Play Music' % (playlist.name, len(track_ids), len(existing_track_ids)))
    if track_ids == existing_track_ids:
        log('Nothing to do')
        return
    tracks_to_remove = set(existing_track_ids) - set(track_ids)
    if tracks_to_remove:
        log('Removing %d songs' % len(tracks_to_remove))
        entry_ids = [e['id'] for e in google_playlist['tracks'] if e['trackId'] in tracks_to_remove]
        api.remove_entries_from_playlist(entry_ids)
        existing_track_ids = [i for i in existing_track_ids if i not in tracks_to_remove]
    # Next, add tracks to the list.
    tracks_to_add = set(track_ids) - set(existing_track_ids)
    if tracks_to_add:
        log('Adding %d songs' % len(tracks_to_add))
        added_songs = api.add_songs_to_playlist(playlist_id, list(tracks_to_add))
        existing_track_ids.extend(added_songs)
    # Finally, reorder the list in Google Play to match the one in iTunes if necessary.
    if track_ids != existing_track_ids:
        log('Reordering songs')
        if tracks_to_add:
            # We need to refresh the playlist first.
            all_google_playlists = api.get_all_user_playlist_contents()
            google_playlist = next(p for p in all_google_playlists if p['id'] == playlist_id)
            existing_track_ids = [t['trackId'] for t in google_playlist['tracks']]
        tracks = google_playlist['tracks']
        sm = difflib.SequenceMatcher(a=existing_track_ids, b=track_ids)
        entries_by_id = defaultdict(list)
        for e in tracks:
            entries_by_id[e['trackId']].append(e)
        names_by_id = {track_ids[i]: t.name for i, t in enumerate(playlist.tracks)}
        for op in sm.get_opcodes():
            if op[0] in ('insert', 'replace'):
                i1, i2, j1, j2 = op[1:]
                follow_entry = None if i1 == 0 else tracks[i1 - 1]
                precede_entry = None if i2 == len(tracks) else tracks[i2]
                for track_id in track_ids[j1:j2]:
                    entry = entries_by_id[track_id].pop(0)
                    log('Moving %s after %s and before %s' % (names_by_id[track_id], 'nothing' if follow_entry is None else names_by_id[follow_entry['trackId']], 'nothing' if precede_entry is None else names_by_id[precede_entry['trackId']]))
                    api.reorder_playlist_entry(entry, to_follow_entry=follow_entry, to_precede_entry=precede_entry)
                    follow_entry = entry

def main():
    parser = argparse.ArgumentParser(description='Sync iTunes Playlists to Google Play Music.')
    parser.add_argument('itunes_music_library', type=str,
                        help='Path to iTunes Music Library.xml')
    parser.add_argument('google_music_manager_db', type=str,
                        help='Path to Google Music Manager ServerDatabase.db')
    parser.add_argument('--verbose', action='store_true', default=False,
                        help='Print verbose output')
    parser.add_argument('playlists', type=str, nargs='*',
                        metavar='playlist',
                        help='Names of playlists to sync')
    args = parser.parse_args()
    global verbose
    verbose = args.verbose
    lib = pyItunes.Library(args.itunes_music_library)
    known_itunes_playlists = lib.getPlaylistNames()
    if args.playlists:
        itunes_playlists = args.playlists
        not_found = set(itunes_playlists) - set(known_itunes_playlists)
        if not_found:
            print('''Error: these playlists aren't in your iTunes Library:
%s
''' % (sorted(not_found), ))
            return 1
    else:
        itunes_playlists = known_itunes_playlists

    server_db = sqlite3.connect(args.google_music_manager_db)
    api = None
    username, password = open(os.path.join(os.path.dirname(__file__),
                                           'auth.txt'),
                              'r').read().splitlines()
    try:
        api = Mobileclient()
        if not api.login(username, password):
            print('Error: unable to login', file=sys.stderr)
            return 1
        all_google_playlists = api.get_all_user_playlist_contents()
        google_playlists = {p['name']: p for p in all_google_playlists}
        for name in itunes_playlists:
            sync_playlist(api, server_db, lib.getPlaylist(name),
                          google_playlists)
    finally:
        if api:
            api.logout()
    return 0

if __name__ == '__main__':
    sys.exit(main())
