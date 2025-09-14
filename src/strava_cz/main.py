import requests


class StravaCZ:
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
            return (
                f"User:\nusername={self.username}, \nfull_name={self.full_name}, "
                "\nemail={self.email}, \nbalance={self.balance}, \ncurrency={self.currency}, "
                "\ncanteen_name={self.canteen_name}, \nsid={self.sid}, "
                "\nis_logged_in={self.is_logged_in}\n"
            )

    def __init__(self, username=None, password=None, canteen_number=None):
        self.session = requests.Session()
        self.base_url = "https://app.strava.cz"
        self.api_url = f"{self.base_url}/api"
        self.login_url = f"{self.api_url}/login"

        self.default_canteen_number = "3753"  # Default canteen number

        self.user = self.User()
        self.orders = []

        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
            ),
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9,de-DE;q=0.8,de;q=0.7,cs;q=0.6",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Content-Type": "text/plain;charset=UTF-8",
            "Origin": "https://app.strava.cz",
            "Referer": "https://app.strava.cz/en/prihlasit-se?jidelna",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
        }

        # Initial GET request to establish session
        self.session.get("https://app.strava.cz/en/prihlasit-se?jidelna")

        if username is not None and password is not None:
            self.login(username=username, password=password, canteen_number=canteen_number)

    def api_request(self, endpoint, payload=None):
        url = f"{self.api_url}/{endpoint}"
        response = self.session.post(url=url, json=payload, headers=self.headers)
        return {"status_code": response.status_code, "response": response.json()}

    def login(self, username, password, canteen_number=None):
        if self.user.is_logged_in:
            raise Exception("User already logged in")
        if not username or not password:
            raise ValueError("Username and password are required for login")

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
            "lang": "EN",
        }

        response = self.api_request("login", payload)

        if response["status_code"] == 200:
            data = response["response"]
            user_data = data.get("uzivatel", {})

            self.user.sid = data.get("sid", "")
            self.user.s5url = data.get("s5url", "")

            self.user.full_name = user_data.get("jmeno", "")
            self.user.email = user_data.get("email", "")
            self.user.balance = user_data.get("konto", 0.0)
            self.user.id = user_data.get("id", 0)
            self.user.currency = user_data.get("mena", "Kč")
            self.user.canteen_name = user_data.get("nazevJidelny", "")

            self.user.is_logged_in = True
            return self.user
        else:
            raise Exception(f"Login failed: {response['response'].get('message', 'Unknown error')}")

    def get_orders_list(self):
        if not self.user.is_logged_in:
            raise Exception("User not logged in")

        payload = {
            "cislo": self.user.canteen_number,
            "sid": self.user.sid,
            "s5url": self.user.s5url,
            "lang": "EN",
            "konto": self.user.balance,
            "podminka": "",
            "ignoreCert": False,
        }

        response = self.api_request("objednavky", payload)

        if response["status_code"] != 200:
            raise Exception("Failed to fetch orders")

        orders_unformated = response["response"]
        self.orders = []

        # Group meals by date
        meals_by_date = {}

        # Iterate through all tables (table0, table1, table2, etc.)
        for table_key, meals_list in orders_unformated.items():
            if not table_key.startswith("table"):
                continue

            for meal in meals_list:
                date = meal["datum"]

                if not meal["nazev"]:
                    continue  # Skip meals without a name

                # Create filtered meal object with only required fields
                meal_filtered = {
                    "local_id": meal["id"],
                    "type": meal["druh_popis"],
                    "name": meal["nazev"],
                    "forbiddenAlergens": meal["zakazaneAlergeny"],
                    "alergens": meal["alergeny"],
                    "ordered": True if meal["pocet"] == 1 else False,
                    "meal_id": int(meal["veta"]),
                }

                # Group by date
                if date not in meals_by_date:
                    meals_by_date[date] = []
                meals_by_date[date].append(meal_filtered)

        # Convert to final format
        for date, meals in meals_by_date.items():
            self.orders.append({"date": date, "meals": meals})

        return self.orders

    # 20, 21

    def is_ordered(self, meal_id):
        if not self.user.is_logged_in:
            raise Exception("User not logged in")

        for day in self.orders:
            for meal in day["meals"]:
                if meal["meal_id"] == meal_id:
                    return meal["ordered"]
        return False

    def add_meal_to_order(self, meal_id):
        if not self.user.is_logged_in:
            raise Exception("User not logged in")

        if not self.orders:
            self.get_orders_list()

        if self.is_ordered(meal_id):
            # Already ordered
            return True

        payload = {
            "cislo": self.user.canteen_number,
            "sid": self.user.sid,
            "url": self.user.s5url,
            "veta": str(meal_id),
            "pocet": 1,
            "lang": "EN",
            "ignoreCert": "false",
        }

        response = self.api_request("pridejJidloS5", payload)
        if response["status_code"] != 200:
            raise Exception("Failed to add meal to order")
        return True

    def save_order(self):
        if not self.user.is_logged_in:
            raise Exception("User not logged in")

        if not self.orders:
            self.get_orders_list()

        payload = {
            "cislo": self.user.canteen_number,
            "sid": self.user.sid,
            "url": self.user.s5url,
            "xml": None,
            "lang": "EN",
            "ignoreCert": "false",
        }

        response = self.api_request("saveOrders", payload)

        if response["status_code"] != 200:
            raise Exception("Failed to save order")
        return True

    def order_meal(self, meal_id):
        self.add_meal_to_order(meal_id)
        self.save_order()
        self.get_orders_list()

    def order_meals(self, *meal_ids):
        for meal_id in meal_ids:
            self.add_meal_to_order(meal_id)
        self.save_order()
        self.get_orders_list()

    def logout(self):
        if not self.user.is_logged_in:
            return True  # Already logged out

        payload = {
            "sid": self.user.sid,
            "cislo": self.user.canteen_number,
            "url": self.user.s5url,
            "lang": "EN",
            "ignoreCert": "false",
        }

        response = self.api_request("logOut", payload)

        if response["status_code"] == 200:
            self.user = self.User()  # Reset user
            self.orders = []  # Clear orders
            return True
        else:
            raise Exception("Failed to logout")
