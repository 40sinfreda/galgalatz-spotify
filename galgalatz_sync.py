#!/usr/bin/env python3
"""
גלגל"צ → Spotify Playlist Sync
מושך שירים מגלגל"צ ומשתול שירים מהרשימה שלך כל 10 שירים.
"""

import os
import json
import time
import random
import requests
import base64
from datetime import datetime
from pathlib import Path

# ─── הגדרות ───────────────────────────────────────────────────────────────────

# רשימת האמנים שלך לשתילה — ערוך כאן!
MY_ARTISTS = [
    "Sean Levine",
    "Marli West",
    "ישראל הדר",
    "Teomic Fire",
]

# כל כמה שירי גלגל"צ לשתול שיר מהרשימה שלך
INSERT_EVERY_N = 10

# גודל מקסימלי לפלייליסט (ספוטיפיי מגביל ל-10,000)
MAX_PLAYLIST_SIZE = 200

# קובץ מצב — עוקב אחרי מה כבר הוספנו
STATE_FILE = Path("state.json")

# ─── Spotify API ───────────────────────────────────────────────────────────────

SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_BASE = "https://api.spotify.com/v1"

# ─── גלגל"צ ───────────────────────────────────────────────────────────────────

GALGALATZ_API = "https://glz.co.il/api/NowPlaying"


def get_spotify_token(client_id: str, client_secret: str, refresh_token: str) -> str:
    """מקבל Access Token מרפרש טוקן."""
    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    resp = requests.post(
        SPOTIFY_TOKEN_URL,
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def get_now_playing_galgalatz() -> dict | None:
    """מושך את השיר הנוכחי מגלגל"צ."""
    try:
        resp = requests.get(GALGALATZ_API, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        # מבנה ה-API של גלגל"צ: {"artist": "...", "title": "...", ...}
        artist = data.get("artist") or data.get("Artist") or data.get("performers")
        title = data.get("title") or data.get("Title") or data.get("songName")
        if artist and title:
            return {"artist": artist.strip(), "title": title.strip()}
    except Exception as e:
        print(f"⚠️  שגיאה במשיכה מגלגל\"צ: {e}")
    return None


def search_spotify_track(token: str, artist: str, title: str) -> str | None:
    """מחפש שיר בספוטיפיי ומחזיר URI."""
    query = f"track:{title} artist:{artist}"
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
    # ניסיון שני — חיפוש פחות מחמיר
    query2 = f"{title} {artist}"
    resp2 = requests.get(
        f"{SPOTIFY_API_BASE}/search",
        headers={"Authorization": f"Bearer {token}"},
        params={"q": query2, "type": "track", "limit": 1, "market": "IL"},
        timeout=10,
    )
    if resp2.status_code == 200:
        items2 = resp2.json().get("tracks", {}).get("items", [])
        if items2:
            return items2[0]["uri"]
    return None


def get_random_track_from_artist(token: str, artist_name: str) -> str | None:
    """מחזיר שיר אקראי מאמן מסוים."""
    # קודם מוצאים את ה-Artist ID
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

    # מושכים top tracks
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

    # מחזירים שיר אקראי מה-top 10
    track = random.choice(tracks[:10])
    return track["uri"]


def get_playlist_track_uris(token: str, playlist_id: str) -> list[str]:
    """מחזיר את כל ה-URIs הנוכחיים בפלייליסט."""
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
        params = {}  # next כבר מכיל את כל הפרמטרים
    return uris


def add_tracks_to_playlist(token: str, playlist_id: str, uris: list[str]) -> bool:
    """מוסיף שירים לפלייליסט."""
    if not uris:
        return True
    # ספוטיפיי מאפשר עד 100 שירים בבקשה אחת
    for i in range(0, len(uris), 100):
        batch = uris[i:i+100]
        resp = requests.post(
            f"{SPOTIFY_API_BASE}/playlists/{playlist_id}/tracks",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"uris": batch},
            timeout=10,
        )
        if resp.status_code not in (200, 201):
            print(f"❌ שגיאה בהוספה לפלייליסט: {resp.text}")
            return False
    return True


def trim_playlist_if_needed(token: str, playlist_id: str, current_uris: list[str]) -> None:
    """מוחק שירים ישנים אם הפלייליסט גדול מדי."""
    if len(current_uris) <= MAX_PLAYLIST_SIZE:
        return
    to_remove = len(current_uris) - MAX_PLAYLIST_SIZE
    tracks_to_remove = [{"uri": uri} for uri in current_uris[:to_remove]]
    print(f"✂️  מוחק {to_remove} שירים ישנים...")
    requests.delete(
        f"{SPOTIFY_API_BASE}/playlists/{playlist_id}/tracks",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"tracks": tracks_to_remove},
        timeout=10,
    )


def load_state() -> dict:
    """טוען מצב קודם מקובץ."""
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {
        "galgalatz_count": 0,      # כמה שירי גלגל"צ נוספו מאז ה"שתילה" האחרונה
        "last_song": None,          # השיר האחרון שהוסף (למניעת כפילויות)
        "added_songs": [],          # כל ה-URIs שנוספו (לבדיקת כפילויות)
        "last_artist_index": -1,    # האמן האחרון ששתלנו ממנו
    }


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))


# ─── לוגיקה ראשית ─────────────────────────────────────────────────────────────

def main():
    # קריאת פרמטרים מ-Environment Variables
    client_id = os.environ["SPOTIFY_CLIENT_ID"]
    client_secret = os.environ["SPOTIFY_CLIENT_SECRET"]
    refresh_token = os.environ["SPOTIFY_REFRESH_TOKEN"]
    playlist_id = os.environ["SPOTIFY_PLAYLIST_ID"]

    print(f"🎵 גלגל\"צ → Spotify | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # אימות ספוטיפיי
    token = get_spotify_token(client_id, client_secret, refresh_token)
    print("✅ מחובר לספוטיפיי")

    # מצב נוכחי
    state = load_state()

    # שירים קיימים בפלייליסט (למניעת כפילויות)
    existing_uris = set(get_playlist_track_uris(token, playlist_id))
    added_set = set(state.get("added_songs", []))
    known_uris = existing_uris | added_set

    # שיר נוכחי מגלגל"צ
    song = get_now_playing_galgalatz()
    if not song:
        print("⚠️  לא ניתן לקרוא מגלגל\"צ כרגע")
        return

    print(f"📻 גלגל\"צ עכשיו: {song['artist']} – {song['title']}")

    # בדיקה אם זה אותו שיר כמו הפעם הקודמת
    song_key = f"{song['artist']}|{song['title']}"
    if state.get("last_song") == song_key:
        print("⏭️  אותו שיר כמו קודם, מדלג")
        return

    tracks_to_add = []

    # מחפשים את שיר גלגל"צ בספוטיפיי
    uri = search_spotify_track(token, song["artist"], song["title"])
    if uri and uri not in known_uris:
        tracks_to_add.append(uri)
        known_uris.add(uri)
        state["galgalatz_count"] += 1
        print(f"➕ נמצא בספוטיפיי: {song['artist']} – {song['title']}")
    elif uri in known_uris:
        print(f"🔁 כבר בפלייליסט: {song['artist']} – {song['title']}")
        state["galgalatz_count"] += 1  # עדיין סופרים
    else:
        print(f"❌ לא נמצא בספוטיפיי: {song['artist']} – {song['title']}")

    # בדיקה אם להוסיף שתילה
    if state["galgalatz_count"] >= INSERT_EVERY_N:
        state["last_artist_index"] = (state["last_artist_index"] + 1) % len(MY_ARTISTS)
        artist_name = MY_ARTISTS[state["last_artist_index"]]
        planted_uri = get_random_track_from_artist(token, artist_name)
        if planted_uri and planted_uri not in known_uris:
            tracks_to_add.append(planted_uri)
            known_uris.add(planted_uri)
            print(f"🌱 שתילה: {artist_name}")
        elif planted_uri:
            print(f"🔁 שתילה כבר קיימת: {artist_name}")
        state["galgalatz_count"] = 0

    # הוספה לפלייליסט
    if tracks_to_add:
        current_uris = get_playlist_track_uris(token, playlist_id)
        trim_playlist_if_needed(token, playlist_id, current_uris)
        if add_tracks_to_playlist(token, playlist_id, tracks_to_add):
            print(f"✅ נוספו {len(tracks_to_add)} שירים לפלייליסט")

    # שמירת מצב
    state["last_song"] = song_key
    state["added_songs"] = list(known_uris)[-500:]  # שומרים 500 אחרונים בלבד
    save_state(state)
    print("💾 מצב נשמר")


if __name__ == "__main__":
    main()
