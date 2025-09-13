import requests
import json
import os
from dotenv import load_dotenv
load_dotenv()

with requests.Session() as s:
    s.get('https://app.strava.cz/en/prihlasit-se?jidelna')

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.9,de-DE;q=0.8,de;q=0.7,cs;q=0.6',
        'Accept-Encoding': 'gzip, deflate, br, zstd',
        'Content-Type': 'text/plain;charset=UTF-8',
        'Origin': 'https://app.strava.cz',
        'Referer': 'https://app.strava.cz/en/prihlasit-se?jidelna',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin'
    }
    
    payload = {
        "cislo": "3753",
        "jmeno": "vojtech.nerad",
        "heslo": os.getenv("TEST_PASSWORD"), 
        "zustatPrihlasen": False,
        "environment": "W",
        "lang": "EN"
    }
    
    url = 'https://app.strava.cz/api/login'

    response = s.post(url=url, json=payload, headers=headers)
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")
