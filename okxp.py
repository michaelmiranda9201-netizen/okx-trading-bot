import ccxt
import pandas as pd
import numpy as np
import requests
import time
import os

# ========================
# CONFIG
# ========================
API_KEY = os.getenv("db75d70b-f577-40e5-b06c-60b9c87584a7")
SECRET = os.getenv("DD0B0C2024162F50F4267C1D59C4AC81")
PASSPHRASE = os.getenv("WXcv8089@")

exchange = ccxt.okx({
    'apiKey': API_KEY,
    'secret': SECRET,
    'password': PASSPHRASE,
    'enableRateLimit': True,
})

# ========================
# NEWS FILTER (TradingEconomics)
# ========================
def high_impact_news():
    try:
        url = "https://api.tradingeconomics.com/calendar"
        r = requests.get(url)
        data = r.json()

        for event in data:
            if event['importance'] == 3:
                return True
        return False
    except:
        return False

# ========================
# INDICADORES
# ========================
def ema(df, period):
    return df['close'].ewm(span=period).mean()

# ========================
# SMART MONEY (simplificado)
# ========================
def detect_liquidity_sweep(df):
    last = df.iloc[-1]
    prev = df.iloc[-2]

    # Sweep de highs
    if last['high'] > prev['high'] and last['close'] < prev['high']:
        return "SELL"

    # Sweep de lows
    if last['low'] < prev['low'] and last['close'] > prev['low']:
        return "BUY"

    return None

def detect_fakeout(df):
    last = df.iloc[-1]

    body = abs(last['close'] - last['open'])
    wick = last['high'] - last['low']

    if wick > body * 3:
        return True

    return False

# ========================
# SCORE
# ========================
def calculate_score(df):
    score = 0

    df['ema50'] = ema(df, 50)
    df['ema200'] = ema(df, 200)

    if df['ema50'].iloc[-1] > df['ema200'].iloc[-1]:
        score += 30
    else:
        score += 30

    if not detect_fakeout(df):
        score += 20

    if df['volume'].iloc[-1] > df['volume'].mean():
        score += 20

    if detect_liquidity_sweep(df):
        score += 30

    return score

# ========================
# SCANNER
# ========================
def get_pairs():
    markets = exchange.load_markets()
    return [s for s in markets if "/USDT" in s]

# ========================
# EJECUCIÓN
# ========================
def run_bot():
    while True:
        print("🔎 Escaneando mercado...")

        if high_impact_news():
            print("⚠️ Noticias fuertes, no operar")
            time.sleep(60)
            continue

        pairs = get_pairs()

        for pair in pairs[:20]:  # limit para rendimiento
            try:
                ohlcv = exchange.fetch_ohlcv(pair, timeframe='15m', limit=100)
                df = pd.DataFrame(ohlcv, columns=['time','open','high','low','close','volume'])

                score = calculate_score(df)
                signal = detect_liquidity_sweep(df)

                if score >= 70 and signal:
                    print(f"🔥 {pair} | {signal} | Score: {score}")

                    # Aquí puedes meter orden real
                    # place_order(pair, signal)

            except Exception as e:
                print(f"Error en {pair}: {e}")

        time.sleep(60)

# ========================
# START
# ========================
if __name__ == "__main__":
    if not API_KEY:
        print("⚠️ Configura tus API KEYS")
    else:
        run_bot()