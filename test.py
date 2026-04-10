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
r2 = requests.get(
    'https://api.spotify.com/v1/playlists/5ADhLOY1Iz8TRXM7VY2sXr/tracks',
    headers={'Authorization': f'Bearer {token}'},
    params={'limit': 5, 'fields': 'items(track(uri,name,artists(name)))', 'market': 'IL'}
)
print(r2.status_code)
print(r2.text[:500])
