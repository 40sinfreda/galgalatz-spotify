import requests

r = requests.get(
    'https://glzxml.blob.core.windows.net/dalet/glglz-onair/onair.xml',
    headers={'User-Agent': 'Mozilla/5.0'}
)
print(r.status_code)
print(r.text[:1000])
