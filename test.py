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

# Get current user ID
me = requests.get('https://api.spotify.com/v1/me', headers={'Authorization': f'Bearer {token}'})
print(me.json().get('id'))
print(me.json().get('display_name'))
