import os
import time
import requests
from okx import Trade

# =============================
# 🔐 API CONFIG
# =============================
API_KEY = os.getenv("db75d70b-f577-40e5-b06c-60b9c87584a7")
SECRET_KEY = os.getenv("DD0B0C2024162F50F4267C1D59C4AC81")
PASSPHRASE = os.getenv("WXcv8089@")

if not API_KEY:
    raise Exception("❌ API KEYS NO CONFIGURADAS")

tradeAPI = Trade.TradeAPI(API_KEY, SECRET_KEY, PASSPHRASE, False, "0")

SYMBOL = "DOGE-USDT-SWAP"
SIZE = "1"

# =============================
# 📊 PRECIO
# =============================
def get_price():
    try:
        url = f"https://www.okx.com/api/v5/market/ticker?instId={SYMBOL}"
        data = requests.get(url).json()
        return float(data["data"][0]["last"])
    except:
        print("❌ Error obteniendo precio")
        return None

# =============================
# 🧠 TENDENCIA SIMPLE
# =============================
last_prices = []

def get_trend(price):
    last_prices.append(price)

    if len(last_prices) > 10:
        last_prices.pop(0)

    if len(last_prices) < 10:
        return "WAIT"

    avg_old = sum(last_prices[:5]) / 5
    avg_new = sum(last_prices[5:]) / 5

    if avg_new > avg_old:
        return "UP"
    elif avg_new < avg_old:
        return "DOWN"
    else:
        return "SIDE"

# =============================
# 🚀 ORDEN
# =============================
def place_order(side):
    print(f"🚀 Enviando orden {side}...")

    try:
        order = tradeAPI.place_order(
            instId=SYMBOL,
            tdMode="cross",
            side=side,
            ordType="market",
            sz=SIZE
        )

        print("📤 OKX RESPONSE:", order)

        if order.get("code") == "0":
            print("✅ ORDEN EJECUTADA")
        else:
            print("❌ OKX ERROR:", order)

    except Exception as e:
        print("❌ ERROR:", e)

# =============================
# 🔁 LOOP
# =============================
while True:
    print("\n🔍 Escaneando...")

    price = get_price()

    if price is None:
        time.sleep(5)
        continue

    print(f"💰 Precio: {price}")

    trend = get_trend(price)

    print(f"📊 Tendencia: {trend}")

    if trend == "UP":
        place_order("buy")

    elif trend == "DOWN":
        place_order("sell")

    else:
        print("⏳ Esperando datos suficientes...")

    time.sleep(30)