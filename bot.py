import requests
import time

BASE_URL = "https://www.okx.com"

def get_price(symbol="BTC-USDT"):
    url = f"{BASE_URL}/api/v5/market/ticker?instId={symbol}"
    response = requests.get(url)
    data = response.json()
    return data["data"][0]["last"]

while True:
    price = get_price("BTC-USDT")
    print("Precio BTC:", price)
    time.sleep(5)
