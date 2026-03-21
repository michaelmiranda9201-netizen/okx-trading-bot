import os
import time
import requests
import pandas as pd
from okx import Trade, Market

# =============================
# 🔐 CONFIG API
# =============================
API_KEY = os.getenv("db75d70b-f577-40e5-b06c-60b9c87584a7")
SECRET_KEY = os.getenv("DD0B0C2024162F50F4267C1D59C4AC81")
PASSPHRASE = os.getenv("WXcv8089@")

if not API_KEY:
    raise ValueError("❌ API KEYS NO CONFIGURADAS")

tradeAPI = Trade.TradeAPI(API_KEY, SECRET_KEY, PASSPHRASE, False, "0")
marketAPI = Market.MarketAPI()

SYMBOL = "DOGE-USDT-SWAP"
SIZE = "1"

# =============================
# 📊 FUNCIONES
# =============================

def get_candles():
    url = f"https://www.okx.com/api/v5/market/candles?instId={SYMBOL}&bar=1m&limit=100"
    data = requests.get(url).json()
    
    df = pd.DataFrame(data["data"])
    df = df.astype(float)
    df.columns = ["ts","open","high","low","close","vol","volCcy","volCcyQuote","confirm"]
    
    return df[::-1]

def calculate_ema(df):
    df["ema50"] = df["close"].ewm(span=50).mean()
    df["ema200"] = df["close"].ewm(span=200).mean()
    return df

def get_trend(df):
    ema50 = df["ema50"].iloc[-1]
    ema200 = df["ema200"].iloc[-1]

    if ema50 > ema200:
        return "UP"
    elif ema50 < ema200:
        return "DOWN"
    else:
        return "SIDE"

# =============================
# 🚀 EJECUCIÓN DE ORDEN
# =============================

def place_order(side):
    print(f"🚀 Intentando abrir {side}...")

    try:
        order = tradeAPI.place_order(
            instId=SYMBOL,
            tdMode="cross",
            side=side,
            ordType="market",
            sz=SIZE
        )

        print("📤 RESPUESTA OKX:", order)

        if order.get("code") == "0":
            print("✅ ORDEN EJECUTADA")
        else:
            print("❌ ERROR DE OKX:", order)

    except Exception as e:
        print("❌ ERROR CRÍTICO:", e)

# =============================
# 🔁 LOOP PRINCIPAL
# =============================

while True:
    try:
        print("\n🔍 Escaneando mercado...")

        df = get_candles()
        df = calculate_ema(df)

        price = df["close"].iloc[-1]
        ema50 = df["ema50"].iloc[-1]
        ema200 = df["ema200"].iloc[-1]

        trend = get_trend(df)

        print(f"📊 Precio: {price}")
        print(f"📈 EMA50: {ema50} | EMA200: {ema200}")

        if trend == "UP":
            print("📈 Tendencia ALCISTA")
            place_order("buy")

        elif trend == "DOWN":
            print("📉 Tendencia BAJISTA")
            place_order("sell")

        else:
            print("⏳ Mercado lateral - sin entrada")

    except Exception as e:
        print("❌ ERROR GENERAL:", e)

    time.sleep(60)