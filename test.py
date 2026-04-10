import requests, base64, os

cid = os.environ['SPOTIFY_CLIENT_ID']
cs = os.environ['SPOTIFY_CLIENT_SECRET']
rt = os.environ['SPOTIFY_REFRESH_TOKEN']

creds = base64.b64encode(f'{cid}:{cs}'.encode()).decode()
r = requests.post(
    'https://accounts.spotify.com/api/token',
    headers={'Authorization': f'Basic {creds}', 'Content-Type': 'application/x-www-form-urlencoded'},
    data={'grant_type': 'refresh_token', 'refresh_token': rt}
)
token = r.json()['access_token']

playlist_id = os.environ['SPOTIFY_PLAYLIST_ID']
r2 = requests.post(
    f'https://api.spotify.com/v1/playlists/{playlist_id}/tracks',
    headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
    json={'uris': ['spotify:track:4iV5W9uYEdYUVa79Axb7Rh']}
)
print(r2.status_code)
print(r2.text)
