import requests
import json
import os
from dotenv import load_dotenv
load_dotenv()

class Strava:
    class User:
        def __init__(self):
            self.username = None
            self.password = None
            self.canteen_number = None
            self.sid = None
            self.s5url = None
            self.full_name = None
            self.email = None
            self.balance = 0.0
            self.id = 0
            self.currency = None
            self.canteen_name = None
            self.is_logged_in = False

        def __repr__(self):
            return f"User:\nusername={self.username}, \nfull_name={self.full_name}, \nemail={self.email}, \nbalance={self.balance}, \ncurrency={self.currency}, \ncanteen_name={self.canteen_name}, \nsid={self.sid}, \nis_logged_in={self.is_logged_in}"

        
    def __init__(self):
        self.session = requests.Session()
        self.base_url = 'https://app.strava.cz'
        self.api_url = f'{self.base_url}/api'
        self.login_url = f'{self.api_url}/login'

        self.default_canteen_number = "3753"  # Default canteen number

        self.user = self.User()

        self.headers = {
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
        
        # Initial GET request to establish session
        self.session.get('https://app.strava.cz/en/prihlasit-se?jidelna')


    def api_request(self, endpoint, payload=None):
        url = f'{self.api_url}/{endpoint}'
        response = self.session.post(url=url, json=payload, headers=self.headers)
        return {'status_code': response.status_code, 'response': response.json()}


    def login(self, username, password, canteen_number=None):
        self.user.username = username
        self.user.password = password
        canteen_number = canteen_number or self.default_canteen_number
        self.user.canteen_number = canteen_number

        payload = {
            "cislo": self.user.canteen_number,
            "jmeno": self.user.username,
            "heslo": self.user.password, 
            "zustatPrihlasen": True,
            "environment": "W",
            "lang": "EN"
        }

        response = self.api_request('login', payload)

        if response['status_code'] == 200:
            data = response['response']
            user_data = data.get('uzivatel', {})
            
            self.user.sid = data.get('sid', '')
            self.user.s5url = data.get('s5url', '')

            self.user.full_name = user_data.get('jmeno', '')
            self.user.email = user_data.get('email', '')
            self.user.balance = user_data.get('konto', 0.0)
            self.user.id = user_data.get('id', 0)
            self.user.currency = user_data.get('mena', 'Kč')
            self.user.canteen_name = user_data.get('nazevJidelny', '')

            self.user.is_logged_in = True
            return self.user
        else:
            return None


app = Strava()

print(app.login("vojtech.nerad", os.getenv("TEST_PASSWORD")))

