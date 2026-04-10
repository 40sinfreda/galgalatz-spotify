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
    f'https://api.spotify.com/v1/playlists/2sCgMi2KCgRfeqWIdjJNxv',
    headers={'Authorization': f'Bearer {token}'}
)
data = r2.json()
print('owner:', data.get('owner', {}).get('id'))
print('my id: 217kazwg6fwmqxf374ivg5fvy')
