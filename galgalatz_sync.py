#!/usr/bin/env python3
"""
Galgalatz -> Spotify Playlist Sync
Creates playlist automatically on first run.
"""

import os
import json
import random
import requests
import base64
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

MY_ARTISTS = [
    "Sean Levine",
    "Marli West",
    "Israel Hadar",
    "Teomic Fire",
]

INSERT_EVERY_N = 10
MAX_PLAYLIST_SIZE = 200
STATE_FILE = Path("state.json")

SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_BASE = "https://api.spotify.com/v1"
GALGALATZ_XML = "https://glzxml.blob.core.windows.net/dalet/glglz-onair/onair.xml"


def get_spotify_token(client_id, client_secret, refresh_token):
    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    resp = requests.post(
        SPOTIFY_TOKEN_URL,
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={"grant_type": "refresh_token", "refresh_token": refresh_token},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def get_current_user_id(token):
    resp = requests.get(
        f"{SPOTIFY_API_BASE}/me",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["id"]


def create_playlist(token, user_id):
    resp = requests.post(
        f"{SPOTIFY_API_BASE}/users/{user_id}/playlists",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"name": "גלגלצ Live", "public": True, "description": "שירים מגלגלצ עם שתילות - נוצר אוטומטית"},
        timeout=10,
    )
    resp.raise_for_status()
    playlist_id = resp.json()["id"]
    print(f"Created new playlist: {playlist_id}")
    return playlist_id


def get_now_playing():
    try:
        resp = requests.get(GALGALATZ_XML, timeout=10)
        resp.raise_for_status()
        root = ET.fromstring(resp.text)
        current = root.find("Current")
        if current is not None:
            title = current.findtext("titleName", "").strip()
            artist = current.findtext("artistName", "").strip()
            if title and artist:
                return {"title": title, "artist": artist}
    except Exception as e:
        print(f"WARNING: Could not fetch Galgalatz XML: {e}")
    return None


def search_spotify_track(token, artist, title):
    for query in [f"track:{title} artist:{artist}", f"{title} {artist}"]:
        resp = requests.get(
            f"{SPOTIFY_API_BASE}/search",
            headers={"Authorization": f"Bearer {token}"},
            params={"q": query, "type": "track", "limit": 1, "market": "IL"},
            timeout=10,
        )
        if resp.status_code == 200:
            items = resp.json().get("tracks", {}).get("items", [])
            if items:
                return items[0]["uri"]
    return None


def get_random_track_from_artist(token, artist_name):
    resp = requests.get(
        f"{SPOTIFY_API_BASE}/search",
        headers={"Authorization": f"Bearer {token}"},
        params={"q": artist_name, "type": "artist", "limit": 1},
        timeout=10,
    )
    if resp.status_code != 200:
        return None
    artists = resp.json().get("artists", {}).get("items", [])
    if not artists:
        return None
    artist_id = artists[0]["id"]
    resp2 = requests.get(
        f"{SPOTIFY_API_BASE}/artists/{artist_id}/top-tracks",
        headers={"Authorization": f"Bearer {token}"},
        params={"market": "IL"},
        timeout=10,
    )
    if resp2.status_code != 200:
        return None
    tracks = resp2.json().get("tracks", [])
    if not tracks:
        return None
    return random.choice(tracks[:10])["uri"]


def get_my_playlist_uris(token, playlist_id):
    uris = []
    url = f"{SPOTIFY_API_BASE}/playlists/{playlist_id}/tracks"
    params = {"fields": "items(track(uri)),next", "limit": 100}
    while url:
        resp = requests.get(url, headers={"Authorization": f"Bearer {token}"}, params=params, timeout=10)
        if resp.status_code != 200:
            break
        data = resp.json()
        for item in data.get("items", []):
            if item.get("track") and item["track"].get("uri"):
                uris.append(item["track"]["uri"])
        url = data.get("next")
        params = {}
    return uris


def add_tracks_to_playlist(token, playlist_id, uris):
    if not uris:
        return True
    for i in range(0, len(uris), 100):
        batch = uris[i:i+100]
        resp = requests.post(
            f"{SPOTIFY_API_BASE}/playlists/{playlist_id}/tracks",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"uris": batch},
            timeout=10,
        )
        if resp.status_code not in (200, 201):
            print(f"ERROR adding to playlist: {resp.text}")
            return False
    return True


def trim_playlist_if_needed(token, playlist_id, current_uris):
    if len(current_uris) <= MAX_PLAYLIST_SIZE:
        return
    to_remove = len(current_uris) - MAX_PLAYLIST_SIZE
    tracks_to_remove = [{"uri": uri} for uri in current_uris[:to_remove]]
    print(f"Trimming {to_remove} old tracks...")
    requests.delete(
        f"{SPOTIFY_API_BASE}/playlists/{playlist_id}/tracks",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"tracks": tracks_to_remove},
        timeout=10,
    )


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {
        "playlist_id": None,
        "galgalatz_count": 0,
        "last_song": None,
        "last_artist_index": -1,
        "seen_uris": [],
    }


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))


def main():
    client_id = os.environ["SPOTIFY_CLIENT_ID"]
    client_secret = os.environ["SPOTIFY_CLIENT_SECRET"]
    refresh_token = os.environ["SPOTIFY_REFRESH_TOKEN"]

    print(f"Galgalatz -> Spotify | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    token = get_spotify_token(client_id, client_secret, refresh_token)
    print("Connected to Spotify")

    state = load_state()

    # Create playlist if it doesn't exist yet
    if not state.get("playlist_id"):
        user_id = get_current_user_id(token)
        playlist_id = create_playlist(token, user_id)
        state["playlist_id"] = playlist_id
        save_state(state)
        print(f"Playlist created! Open it at: https://open.spotify.com/playlist/{playlist_id}")
    else:
        playlist_id = state["playlist_id"]
        print(f"Using playlist: {playlist_id}")

    seen_uris = set(state.get("seen_uris", []))
    my_uris = set(get_my_playlist_uris(token, playlist_id))
    known_uris = seen_uris | my_uris

    song = get_now_playing()
    if not song:
        print("Could not read from Galgalatz, skipping")
        save_state(state)
        return

    print(f"Now playing: {song['artist']} - {song['title']}")

    song_key = f"{song['artist']}|{song['title']}"
    if state.get("last_song") == song_key:
        print("Same song as last time, skipping")
        save_state(state)
        return

    tracks_to_add = []

    uri = search_spotify_track(token, song["artist"], song["title"])
    if uri and uri not in known_uris:
        tracks_to_add.append(uri)
        known_uris.add(uri)
        state["galgalatz_count"] += 1
        print(f"Found: {song['artist']} - {song['title']}")
    elif uri:
        print(f"Already in playlist: {song['artist']} - {song['title']}")
        state["galgalatz_count"] += 1
    else:
        print(f"Not found on Spotify: {song['artist']} - {song['title']}")

    if state["galgalatz_count"] >= INSERT_EVERY_N:
        state["last_artist_index"] = (state["last_artist_index"] + 1) % len(MY_ARTISTS)
        artist_name = MY_ARTISTS[state["last_artist_index"]]
        planted_uri = get_random_track_from_artist(token, artist_name)
        if planted_uri and planted_uri not in known_uris:
            tracks_to_add.append(planted_uri)
            known_uris.add(planted_uri)
            print(f"** Planted: {artist_name}")
        state["galgalatz_count"] = 0

    if tracks_to_add:
        current_uris = get_my_playlist_uris(token, playlist_id)
        trim_playlist_if_needed(token, playlist_id, current_uris)
        if add_tracks_to_playlist(token, playlist_id, tracks_to_add):
            print(f"Added {len(tracks_to_add)} track(s)!")

    state["last_song"] = song_key
    state["seen_uris"] = list(known_uris)[-1000:]
    save_state(state)
    print("Done!")


if __name__ == "__main__":
    main()
