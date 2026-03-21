import os
import time
import requests
import hmac
import base64
import hashlib
import json
from datetime import datetime

# =============================
# 🔐 CONFIG
# =============================
API_KEY = os.getenv("db75d70b-f577-40e5-b06c-60b9c87584a7")
SECRET_KEY = os.getenv("DD0B0C2024162F50F4267C1D59C4AC81")
PASSPHRASE = os.getenv("WXcv8089@")

if not API_KEY:
    raise Exception("❌ API KEYS NO CONFIGURADAS")

BASE_URL = "https://www.okx.com"
SYMBOL = "DOGE-USDT-SWAP"

# =============================
# 🔑 FIRMA OKX
# =============================
def sign(message, secret):
    return base64.b64encode(
        hmac.new(secret.encode(), message.encode(), hashlib.sha256).digest()
    ).decode()

def get_headers(method, path, body=""):
    timestamp = datetime.utcnow().isoformat("T", "milliseconds") + "Z"
    message = timestamp + method + path + body

    return {
        "OK-ACCESS-KEY": API_KEY,
        "OK-ACCESS-SIGN": sign(message, SECRET_KEY),
        "OK-ACCESS-TIMESTAMP": timestamp,
        "OK-ACCESS-PASSPHRASE": PASSPHRASE,
        "Content-Type": "application/json"
    }

# =============================
# 📊 PRECIO
# =============================
def get_price():
    try:
        url = f"{BASE_URL}/api/v5/market/ticker?instId={SYMBOL}"
        data = requests.get(url).json()
        return float(data["data"][0]["last"])
    except:
        print("❌ Error precio")
        return None

# =============================
# 🚀 ORDEN
# =============================
def place_order(side):
    path = "/api/v5/trade/order"

    body = json.dumps({
        "instId": SYMBOL,
        "tdMode": "cross",
        "side": side,
        "ordType": "market",
        "sz": "1"
    })

    headers = get_headers("POST", path, body)

    try:
        res = requests.post(BASE_URL + path, headers=headers, data=body)
        data = res.json()

        print("📤 RESPUESTA OKX:", data)

        if data.get("code") == "0":
            print("✅ ORDEN EJECUTADA")
        else:
            print("❌ ERROR:", data)

    except Exception as e:
        print("❌ ERROR CRÍTICO:", e)

# =============================
# 🔁 LOOP SIMPLE
# =============================
last_price = None

while True:
    print("\n🔍 Escaneando...")

    price = get_price()

    if price is None:
        time.sleep(5)
        continue

    print(f"💰 Precio: {price}")

    if last_price:
        if price > last_price:
            print("📈 SUBIENDO → BUY")
            place_order("buy")

        elif price < last_price:
            print("📉 BAJANDO → SELL")
            place_order("sell")

    last_price = price

    time.sleep(20)