#!/usr/bin/env python3
"""
Galgalatz -> Spotify Playlist Sync
"""

import os
import json
import re
import random
import requests
import base64
from datetime import datetime
from pathlib import Path

# --- Your artists to plant every 10 Galgalatz songs ---
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
GALGALATZ_URL = "https://radio.menu/stations/glz-co-il-galgalatz/playlist/"


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


def get_now_playing_galgalatz():
    """Fetch latest song played on Galgalatz from radio.menu."""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(GALGALATZ_URL, headers=headers, timeout=10)
        resp.raise_for_status()
        html = resp.text
        # Look for lines like: HH:MM Artist - Title
        matches = re.findall(r'\d{2}:\d{2}\s+(.+?)\s*[-\u2013]\s*(.+?)(?=\s*\d{2}:\d{2}|\s*<|\n)', html)
        if matches:
            artist = re.sub(r'<[^>]+>', '', matches[0][0]).strip()
            title = re.sub(r'<[^>]+>', '', matches[0][1]).strip()
            if artist and title:
                print(f"Radio: {artist} - {title}")
                return {"artist": artist, "title": title}
    except Exception as e:
        print(f"WARNING: Could not fetch Galgalatz: {e}")
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


def get_playlist_track_uris(token, playlist_id):
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
    return {"galgalatz_count": 0, "last_song": None, "added_songs": [], "last_artist_index": -1}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))


def main():
    client_id = os.environ["SPOTIFY_CLIENT_ID"]
    client_secret = os.environ["SPOTIFY_CLIENT_SECRET"]
    refresh_token = os.environ["SPOTIFY_REFRESH_TOKEN"]
    playlist_id = os.environ["SPOTIFY_PLAYLIST_ID"]

    print(f"Galgalatz -> Spotify | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    token = get_spotify_token(client_id, client_secret, refresh_token)
    print("Connected to Spotify")

    state = load_state()
    existing_uris = set(get_playlist_track_uris(token, playlist_id))
    known_uris = existing_uris | set(state.get("added_songs", []))

    song = get_now_playing_galgalatz()
    if not song:
        print("Could not read from Galgalatz, skipping")
        return

    song_key = f"{song['artist']}|{song['title']}"
    if state.get("last_song") == song_key:
        print("Same song as last time, skipping")
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
            print(f"Planting song from: {artist_name}")
        state["galgalatz_count"] = 0

    if tracks_to_add:
        current_uris = get_playlist_track_uris(token, playlist_id)
        trim_playlist_if_needed(token, playlist_id, current_uris)
        if add_tracks_to_playlist(token, playlist_id, tracks_to_add):
            print(f"Added {len(tracks_to_add)} track(s) to playlist")

    state["last_song"] = song_key
    state["added_songs"] = list(known_uris)[-500:]
    save_state(state)
    print("State saved. Done!")


if __name__ == "__main__":
    main()
