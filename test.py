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

# Create new playlist
r2 = requests.post(
    'https://api.spotify.com/v1/users/217kazwg6fwmqxf374ivg5fvy/playlists',
    headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
    json={'name': 'גלגלצ Live', 'public': True, 'description': 'שירים מגלגלצ עם שתילות'}
)
print(r2.status_code)
print(r2.json().get('id'))
print(r2.json().get('external_urls', {}).get('spotify'))
