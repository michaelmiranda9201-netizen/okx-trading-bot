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
MAX_ORDERS_PER_PAIR = 6
COOLDOWN = 600  # segundos

last_trade_time = {}

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
def candles(symbol, tf):
    try:
        url = f"/api/v5/market/candles?instId={symbol}&bar={tf}&limit=100"
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

def get_pairs():
    try:
        r = requests.get(BASE_URL + "/api/v5/public/instruments?instType=SWAP").json()
        return [i['instId'] for i in r.get('data', []) if "USDT" in i['instId']]
    except:
        return []

# =========================
# INDICADORES
# =========================
def ema(df, n):
    return df['c'].ewm(span=n).mean()

def atr(df):
    return (df['h'] - df['l']).rolling(14).mean()

# =========================
# MODO MERCADO
# =========================
def get_mode(symbol):
    h4 = candles(symbol, "4H")
    h1 = candles(symbol, "1H")

    if h4 is None or h1 is None or len(h4) < 50 or len(h1) < 50:
        return None

    h4['ema50'], h4['ema200'] = ema(h4,50), ema(h4,200)
    h1['ema50'], h1['ema200'] = ema(h1,50), ema(h1,200)

    if h4['ema50'].iloc[-1] > h4['ema200'].iloc[-1] and h1['ema50'].iloc[-1] > h1['ema200'].iloc[-1]:
        return "long"
    elif h4['ema50'].iloc[-1] < h4['ema200'].iloc[-1] and h1['ema50'].iloc[-1] < h1['ema200'].iloc[-1]:
        return "short"
    return "neutral"

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
# ORDENES ABIERTAS
# =========================
def open_orders(symbol):
    try:
        path = f"/api/v5/trade/orders-pending?instId={symbol}"
        r = requests.get(BASE_URL + path, headers=headers("GET", path)).json()
        return r.get('data', [])
    except:
        return []

# =========================
# GRID + TP/SL
# =========================
def build_orders(symbol, price, atr_val, mode):
    orders = []
    step = atr_val * 0.5

    for i in range(1, 4):
        if mode == "long":
            entry = price - step * i
            sl = entry - atr_val * 1.2
            tp = entry + atr_val * 2.5
            side = "buy"

        elif mode == "short":
            entry = price + step * i
            sl = entry + atr_val * 1.2
            tp = entry - atr_val * 2.5
            side = "sell"

        else:
            continue

        orders.append((side, entry, sl, tp))

    return orders

# =========================
# EJECUTAR ORDEN
# =========================
def place_order(symbol, side, px, sl, tp):
    body = json.dumps({
        "instId": symbol,
        "tdMode": "isolated",
        "side": side,
        "ordType": "limit",
        "px": str(px),
        "sz": "0.01",
        "lever": "3",
        "slTriggerPx": str(sl),
        "tpTriggerPx": str(tp)
    })

    path = "/api/v5/trade/order"

    try:
        requests.post(BASE_URL + path,
            headers=headers("POST", path, body),
            data=body)

        print(f"🔥 {symbol} {side} @ {px} | SL {sl} | TP {tp}")

    except Exception as e:
        print("Error orden:", e)

# =========================
# RUN
# =========================
def run():
    pairs = get_pairs()
    open_pos = len(positions())

    for symbol in pairs:

        if open_pos >= MAX_TRADES:
            return

        # cooldown
        if symbol in last_trade_time:
            if time.time() - last_trade_time[symbol] < COOLDOWN:
                continue

        try:
            m5 = candles(symbol, "5M")
            if m5 is None or len(m5) < 30:
                continue

            price = m5['c'].iloc[-1]

            atr_series = atr(m5)
            if atr_series is None or len(atr_series) < 20:
                continue

            atr_val = atr_series.iloc[-1]
            if pd.isna(atr_val) or atr_val == 0:
                continue

            # filtro volatilidad mínima
            if atr_val < price * 0.001:
                continue

            mode = get_mode(symbol)
            if mode not in ["long", "short"]:
                continue

            # evitar duplicados
            if len(open_orders(symbol)) > MAX_ORDERS_PER_PAIR:
                continue

            orders = build_orders(symbol, price, atr_val, mode)

            for o in orders:
                place_order(symbol, o[0], o[1], o[2], o[3])

            last_trade_time[symbol] = time.time()
            open_pos += 1

            print(f"⚡ {symbol} MODE: {mode}")

            time.sleep(1)

        except Exception as e:
            print(f"Error {symbol}:", e)

# =========================
# LOOP
# =========================
while True:
    try:
        print("💀 KILLER CONTROL ACTIVO...")
        run()
        time.sleep(180)
    except Exception as e:
        print("💥 Error general:", e)
        time.sleep(60)