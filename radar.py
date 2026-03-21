import os
import time
import ccxt
import pandas as pd
import numpy as np

# ========================
# CONFIG
# ========================
SYMBOL = "BTC/USDT:USDT"
TIMEFRAME = "1m"
MAX_TRADES = 4
GRID_SIZE = 4
RISK_PER_TRADE = 0.02
LEVERAGE = 5

# ========================
# API
# ========================
api_key = os.getenv("db75d70b-f577-40e5-b06c-60b9c87584a7")
secret = os.getenv("DD0B0C2024162F50F4267C1D59C4AC81")
password = os.getenv("WXcv8089@")

if not api_key:
    raise ValueError("❌ API KEYS NO CONFIGURADAS")

exchange = ccxt.okx({
    'apiKey': api_key,
    'secret': secret,
    'password': password,
    'enableRateLimit': True,
})

exchange.set_sandbox_mode(False)

# ========================
# DATA
# ========================
def get_data():
    ohlcv = exchange.fetch_ohlcv(SYMBOL, TIMEFRAME, limit=100)
    df = pd.DataFrame(ohlcv, columns=['time','open','high','low','close','volume'])
    return df

# ========================
# INDICADORES
# ========================
def indicators(df):
    df['ema50'] = df['close'].ewm(span=50).mean()
    df['ema200'] = df['close'].ewm(span=200).mean()
    df['rsi'] = 100 - (100 / (1 + df['close'].pct_change().rolling(14).mean()))
    df['volatility'] = df['close'].pct_change().rolling(10).std()
    return df

# ========================
# IA (FILTRO AVANZADO)
# ========================
def ai_filter(df):
    last = df.iloc[-1]

    momentum = last['close'] - df['close'].iloc[-5]
    volatility = last['volatility']

    # Detectar fake breakout
    fakeout = abs(last['high'] - last['close']) > abs(last['close'] - last['low'])

    if volatility < 0.001:
        return False

    if fakeout:
        return False

    if abs(momentum) < 10:
        return False

    return True

# ========================
# TREND
# ========================
def get_trend(df):
    last = df.iloc[-1]
    if last['ema50'] > last['ema200']:
        return "bullish"
    else:
        return "bearish"

# ========================
# POSICIONES ABIERTAS
# ========================
def open_positions():
    try:
        positions = exchange.fetch_positions([SYMBOL])
        active = [p for p in positions if float(p['contracts']) > 0]
        return active
    except:
        return []

# ========================
# GRID ENGINE
# ========================
def place_grid(trend, price):
    size = 0.001  # Ajustado para cuentas pequeñas

    for i in range(GRID_SIZE):
        offset = (i + 1) * 50  # distancia del grid

        if trend == "bullish":
            entry = price - offset
            side = "buy"
        else:
            entry = price + offset
            side = "sell"

        try:
            exchange.create_limit_order(
                SYMBOL,
                side,
                size,
                entry,
                params={
                    "tdMode": "isolated",
                    "lever": LEVERAGE
                }
            )
            print(f"✅ Orden {side} en {entry}")
        except Exception as e:
            print("❌ Error orden:", e)

# ========================
# LOOP PRINCIPAL
# ========================
def run():
    print("🚀 BOT GRID IA INICIADO")

    while True:
        try:
            df = get_data()
            df = indicators(df)

            trend = get_trend(df)
            price = df['close'].iloc[-1]

            positions = open_positions()

            print(f"📊 Precio: {price} | Trend: {trend} | Trades: {len(positions)}")

            if len(positions) >= MAX_TRADES:
                print("⛔ Máximo de trades alcanzado")
                time.sleep(10)
                continue

            if not ai_filter(df):
                print("🧠 IA: No operar (filtro activo)")
                time.sleep(10)
                continue

            print("🔥 IA confirma entrada")

            place_grid(trend, price)

            time.sleep(15)

        except Exception as e:
            print("❌ Error:", e)
            time.sleep(10)

# ========================
# START
# ========================
if __name__ == "__main__":
    run()