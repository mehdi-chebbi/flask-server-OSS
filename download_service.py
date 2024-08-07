# download_service.py

import requests

class DownloadService:
    def __init__(self, token_url, username, password, client_id):
        self.token_url = token_url
        self.username = username
        self.password = password
        self.client_id = client_id

    def get_access_token(self):
        data = {
            "grant_type": "password",
            "username": self.username,
            "password": self.password,
            "client_id": self.client_id
        }
        response = requests.post(self.token_url, data=data)
        if response.status_code == 200:
            return response.json().get('access_token')
        else:
            print(f"Failed to get access token. Status code: {response.status_code}")
            return None

    def refresh_access_token(self, refresh_token):
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.client_id
        }
        response = requests.post(self.token_url, data=data)
        if response.status_code == 200:
            return response.json().get('access_token')
        else:
            print(f"Failed to refresh token. Status code: {response.status_code}")
            return None

    def download_product(self, product_id, access_token):
        headers = {"Authorization": f"Bearer {access_token}"}
        session = requests.Session()
        session.headers.update(headers)
        download_url = f"https://download.dataspace.copernicus.eu/odata/v1/Products({product_id})/$value"
        response = session.get(download_url, stream=True)
        if response.status_code == 401:
            # Handle token refresh and retry
            pass
        return response
