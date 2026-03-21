import os
import time
import requests
import hmac
import base64
import hashlib
import json
from datetime import datetime

# =============================
# 🔐 CONFIGURACIÓN SEGURA
# =============================
API_KEY = os.environ.get("db75d70b-f577-40e5-b06c-60b9c87584a7")
SECRET_KEY = os.environ.get("DD0B0C2024162F50F4267C1D59C4AC81")
PASSPHRASE = os.environ.get("WXcv8089@")

print("🔐 Verificando API Keys...")

if not API_KEY or not SECRET_KEY or not PASSPHRASE:
    print("❌ ERROR: FALTAN API KEYS")
    print("👉 Verifica en Railway > Variables:")
    print("OKX_API_KEY, OKX_SECRET_KEY, OKX_PASSPHRASE")
    time.sleep(999999)  # evita que el contenedor crashee
else:
    print("✅ API Keys detectadas")

BASE_URL = "https://www.okx.com"
SYMBOL = "DOGE-USDT-SWAP"
SIZE = "1"

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
        res = requests.get(url)
        data = res.json()

        if "data" not in data:
            print("❌ Error API:", data)
            return None

        return float(data["data"][0]["last"])

    except Exception as e:
        print("❌ ERROR PRECIO:", e)
        return None

# =============================
# 🚀 ORDEN
# =============================
def place_order(side):
    print(f"🚀 Intentando {side.upper()}")

    path = "/api/v5/trade/order"

    body_dict = {
        "instId": SYMBOL,
        "tdMode": "cross",
        "side": side,
        "ordType": "market",
        "sz": SIZE
    }

    body = json.dumps(body_dict)
    headers = get_headers("POST", path, body)

    try:
        res = requests.post(BASE_URL + path, headers=headers, data=body)
        data = res.json()

        print("📤 RESPUESTA OKX:", data)

        if data.get("code") == "0":
            print("✅ ORDEN EJECUTADA")
        else:
            print("❌ ERROR OKX:", data)

    except Exception as e:
        print("❌ ERROR ORDEN:", e)

# =============================
# 🧠 LÓGICA SIMPLE
# =============================
last_price = None

def check_signal(price):
    global last_price

    if last_price is None:
        last_price = price
        return None

    if price > last_price:
        last_price = price
        return "buy"

    elif price < last_price:
        last_price = price
        return "sell"

    return None

# =============================
# 🔁 LOOP PRINCIPAL
# =============================
print("🤖 BOT INICIADO")

while True:
    try:
        print("\n🔍 Escaneando mercado...")

        price = get_price()

        if price is None:
            time.sleep(10)
            continue

        print(f"💰 Precio actual: {price}")

        signal = check_signal(price)

        if signal:
            print(f"📊 Señal detectada: {signal.upper()}")
            place_order(signal)
        else:
            print("⏳ Esperando movimiento...")

    except Exception as e:
        print("❌ ERROR GENERAL:", e)

    time.sleep(20)