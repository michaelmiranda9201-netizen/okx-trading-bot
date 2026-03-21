import requests
import time
import hmac
import base64
import json
import os
from datetime import datetime
import pandas as pd

# =========================
# CONFIG
# =========================
API_KEY = os.getenv("db75d70b-f577-40e5-b06c-60b9c87584a7")
SECRET_KEY = os.getenv("DD0B0C2024162F50F4267C1D59C4AC81")
PASSPHRASE = os.getenv("WXcv8089@")

BASE_URL = "https://www.okx.com"
SYMBOL = "BTC-USDT-SWAP"

SIZE = "0.01"  # 🔥 tamaño mínimo seguro

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
def candles(tf):
    try:
        url = f"/api/v5/market/candles?instId={SYMBOL}&bar={tf}&limit=100"
        r = requests.get(BASE_URL + url).json()

        if 'data' not in r or len(r['data']) == 0:
            return None

        df = pd.DataFrame(r['data'],
            columns=['ts','o','h','l','c','vol','v1','v2','conf'])

        df = df[::-1]
        df[['c','h','l']] = df[['c','h','l']].astype(float)
        return df
    except:
        return None

# =========================
# INDICADORES
# =========================
def ema(df, n):
    return df['c'].ewm(span=n).mean()

def atr(df):
    return (df['h'] - df['l']).rolling(14).mean()

# =========================
# IA MODO MERCADO
# =========================
def get_mode():
    h4 = candles("4H")
    h1 = candles("1H")

    if h4 is None or h1 is None:
        return None

    h4['ema50'], h4['ema200'] = ema(h4,50), ema(h4,200)
    h1['ema50'], h1['ema200'] = ema(h1,50), ema(h1,200)

    if h4['ema50'].iloc[-1] > h4['ema200'].iloc[-1]:
        return "long"
    elif h4['ema50'].iloc[-1] < h4['ema200'].iloc[-1]:
        return "short"
    return "neutral"

# =========================
# APALANCAMIENTO
# =========================
def get_leverage(atr_val, price):
    ratio = atr_val / price

    if ratio > 0.001:
        return "3"
    elif ratio > 0.0005:
        return "5"
    return "7"

# =========================
# ORDEN LIMIT (GRID REAL)
# =========================
def place_order(side, px, sl, tp, lev):

    body = json.dumps({
        "instId": SYMBOL,
        "tdMode": "isolated",
        "side": side,
        "ordType": "limit",
        "px": str(px),
        "sz": SIZE,
        "lever": lev,
        "slTriggerPx": str(sl),
        "tpTriggerPx": str(tp)
    })

    path = "/api/v5/trade/order"

    r = requests.post(BASE_URL + path,
        headers=headers("POST", path, body),
        data=body)

    print("ORDER:", r.json())

# =========================
# GRID REAL
# =========================
def grid(price, atr_val, mode):

    step = atr_val * 0.3
    lev = get_leverage(atr_val, price)

    for i in range(1, 4):

        if mode == "long":
            entry = price - step * i
            place_order(
                "buy",
                entry,
                entry - atr_val,
                entry + atr_val * 2,
                lev
            )

        elif mode == "short":
            entry = price + step * i
            place_order(
                "sell",
                entry,
                entry + atr_val,
                entry - atr_val * 2,
                lev
            )

        else:
            buy = price - step * i
            sell = price + step * i

            place_order("buy", buy, buy - atr_val, buy + atr_val * 2, lev)
            place_order("sell", sell, sell + atr_val, sell - atr_val * 2, lev)

# =========================
# PROFIT LOCK (BÁSICO)
# =========================
def profit_lock(price, atr_val, mode):
    if mode == "long":
        print(f"🔒 SL dinámico sugerido: {price - atr_val * 0.5}")
    elif mode == "short":
        print(f"🔒 SL dinámico sugerido: {price + atr_val * 0.5}")

# =========================
# RUN
# =========================
def run():

    m5 = candles("5M")

    if m5 is None or len(m5) < 50:
        return

    price = m5['c'].iloc[-1]
    atr_val = atr(m5).iloc[-1]

    if pd.isna(atr_val) or atr_val == 0:
        return

    mode = get_mode()

    print(f"🧠 MODE: {mode} | PRICE: {price}")

    # 🔥 ejecutar grid
    grid(price, atr_val, mode)

    # 🔒 profit lock info
    profit_lock(price, atr_val, mode)

# =========================
# LOOP
# =========================
while True:
    try:
        print("💀 BTC GRID SNIPER IA ACTIVO...")
        run()
        time.sleep(120)
    except Exception as e:
        print("ERROR:", e)
        time.sleep(60)