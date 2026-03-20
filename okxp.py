import requests
import time
import hmac
import base64
import json
import os
from datetime import datetime
import pandas as pd

API_KEY = os.getenv("db75d70b-f577-40e5-b06c-60b9c87584a7")
SECRET_KEY = os.getenv("DD0B0C2024162F50F4267C1D59C4AC81")
PASSPHRASE = os.getenv("WXcv8089@")

BASE_URL = "https://www.okx.com"

MAX_TRADES = 4
CAPITAL = 50
RISK = 0.02

# =========================
# AUTH
# =========================
def headers(method, path, body=""):
    ts = datetime.utcnow().isoformat() + "Z"
    msg = ts + method + path + body
    sign = base64.b64encode(
        hmac.new(SECRET_KEY.encode(), msg.encode(), 'sha256').digest()
    )
    return {
        "OK-ACCESS-KEY": API_KEY,
        "OK-ACCESS-SIGN": sign.decode(),
        "OK-ACCESS-TIMESTAMP": ts,
        "OK-ACCESS-PASSPHRASE": PASSPHRASE,
        "Content-Type": "application/json"
    }

# =========================
# DATA
# =========================
def get_pairs():
    r = requests.get(BASE_URL + "/api/v5/public/instruments?instType=SWAP").json()
    return [i['instId'] for i in r['data'] if "USDT" in i['instId']]

def candles(symbol, tf):
    url = f"/api/v5/market/candles?instId={symbol}&bar={tf}&limit=100"
    r = requests.get(BASE_URL + url).json()
    df = pd.DataFrame(r['data'],
        columns=['ts','o','h','l','c','vol','v1','v2','conf'])
    df = df[::-1]
    df[['c','h','l']] = df[['c','h','l']].astype(float)
    return df

# =========================
# INDICADORES
# =========================
def ema(df, n):
    return df['c'].ewm(span=n).mean()

def atr(df):
    return (df['h'] - df['l']).rolling(14).mean()

# =========================
# TENDENCIA
# =========================
def get_mode(symbol):
    h4 = candles(symbol, "4H")
    h1 = candles(symbol, "1H")

    h4['ema50'], h4['ema200'] = ema(h4,50), ema(h4,200)
    h1['ema50'], h1['ema200'] = ema(h1,50), ema(h1,200)

    if h4['ema50'].iloc[-1] > h4['ema200'].iloc[-1] and h1['ema50'].iloc[-1] > h1['ema200'].iloc[-1]:
        return "long"
    elif h4['ema50'].iloc[-1] < h4['ema200'].iloc[-1] and h1['ema50'].iloc[-1] < h1['ema200'].iloc[-1]:
        return "short"
    return "neutral"

# =========================
# GRID LOGIC
# =========================
def build_grid(price, atr_val, mode):
    grid = []
    step = atr_val * 0.5

    for i in range(1, 4):
        if mode == "long":
            grid.append(price - step * i)
        elif mode == "short":
            grid.append(price + step * i)
        else:
            grid.append(price - step * i)
            grid.append(price + step * i)

    return grid

# =========================
# POSICIONES
# =========================
def positions():
    try:
        path = "/api/v5/account/positions"
        r = requests.get(BASE_URL + path, headers=headers("GET", path)).json()
        return [p for p in r.get('data', []) if float(p.get('pos', 0)) != 0]
    except:
        return []

# =========================
# ORDEN
# =========================
def place_order(symbol, side, price):
    body = json.dumps({
        "instId": symbol,
        "tdMode": "isolated",
        "side": side,
        "ordType": "limit",
        "px": str(price),
        "sz": "0.01",
        "lever": "3"
    })

    path = "/api/v5/trade/order"

    try:
        r = requests.post(BASE_URL + path,
            headers=headers("POST", path, body),
            data=body)

        print(f"GRID {symbol} {side} @ {price}")

    except Exception as e:
        print("Error orden:", e)

# =========================
# SCANNER + GRID
# =========================
def run():
    pairs = get_pairs()
    open_pos = len(positions())

    for symbol in pairs:
        if open_pos >= MAX_TRADES:
            return

        try:
            m5 = candles(symbol, "5M")
            price = m5['c'].iloc[-1]
            atr_val = atr(m5).iloc[-1]

            if atr_val is None or atr_val == 0:
                continue

            mode = get_mode(symbol)

            grid = build_grid(price, atr_val, mode)

            for g in grid:
                if mode == "long":
                    place_order(symbol, "buy", g)
                elif mode == "short":
                    place_order(symbol, "sell", g)
                else:
                    place_order(symbol, "buy", g)
                    place_order(symbol, "sell", g)

            open_pos += 1
            time.sleep(1)

        except Exception as e:
            print(f"Error {symbol}:", e)

# =========================
# LOOP
# =========================
while True:
    try:
        print("⚡ ULTRA SCALPING RUNNING...")
        run()
        time.sleep(180)
    except Exception as e:
        print("💥 Error:", e)
        time.sleep(60)