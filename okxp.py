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
SYMBOL = "BTC-USDT-SWAP"

CAPITAL = 50
RISK = 0.02

last_trade = 0
COOLDOWN = 60  # 1 min

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
    url = f"/api/v5/market/candles?instId={SYMBOL}&bar={tf}&limit=200"
    r = requests.get(BASE_URL + url).json()

    if 'data' not in r:
        return None

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
# IA AVANZADA
# =========================
def ai_signal():
    h4 = candles("4H")
    h1 = candles("1H")
    m1 = candles("1m")

    if h4 is None or h1 is None or m1 is None:
        return None

    # tendencia mayor
    h4['ema50'], h4['ema200'] = ema(h4,50), ema(h4,200)
    h1['ema50'], h1['ema200'] = ema(h1,50), ema(h1,200)

    trend = None
    if h4['ema50'].iloc[-1] > h4['ema200'].iloc[-1]:
        trend = "bull"
    else:
        trend = "bear"

    # momentum 1M
    m1['ema20'] = ema(m1, 20)
    momentum = m1['c'].iloc[-1] - m1['ema20'].iloc[-1]

    # micro estructura
    last = m1['c'].iloc[-1]
    prev = m1['c'].iloc[-2]

    atr_val = atr(m1).iloc[-1]

    if pd.isna(atr_val) or atr_val == 0:
        return None

    volatility = atr_val / last

    # =========================
    # LÓGICA IA
    # =========================
    if trend == "bull" and momentum > 0 and last > prev and volatility > 0.0003:
        return "buy", atr_val

    if trend == "bear" and momentum < 0 and last < prev and volatility > 0.0003:
        return "sell", atr_val

    return None

# =========================
# LEVERAGE
# =========================
def get_leverage(atr_val, price):
    ratio = atr_val / price

    if ratio > 0.001:
        return 3
    elif ratio > 0.0005:
        return 5
    return 7

# =========================
# SIZE
# =========================
def size(price, sl):
    risk_amt = CAPITAL * RISK
    dist = abs(price - sl)
    if dist == 0:
        return 0
    return round(risk_amt / dist, 4)

# =========================
# ORDEN
# =========================
def trade(side, atr_val):
    m1 = candles("1m")
    price = m1['c'].iloc[-1]

    lev = get_leverage(atr_val, price)

    if side == "buy":
        sl = price - atr_val * 0.8
        tp = price + atr_val * 2
    else:
        sl = price + atr_val * 0.8
        tp = price - atr_val * 2

    sz = size(price, sl)

    body = json.dumps({
        "instId": SYMBOL,
        "tdMode": "isolated",
        "side": side,
        "ordType": "market",
        "sz": str(sz),
        "lever": str(lev),
        "slTriggerPx": str(sl),
        "tpTriggerPx": str(tp)
    })

    path = "/api/v5/trade/order"

    r = requests.post(BASE_URL + path,
        headers=headers("POST", path, body),
        data=body)

    print(f"🚀 {side} | lev {lev} | {r.json()}")

# =========================
# LOOP
# =========================
while True:
    try:
        print("💀 BTC SNIPER IA V2 ACTIVO...")

        if time.time() - last_trade < COOLDOWN:
            time.sleep(5)
            continue

        signal = ai_signal()

        if signal:
            side, atr_val = signal
            trade(side, atr_val)
            last_trade = time.time()

        time.sleep(5)

    except Exception as e:
        print("Error:", e)
        time.sleep(10)