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

SIZE = "0.01"
GRID_LEVELS = 5

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

        if 'data' not in r:
            print(f"❌ Sin datos {tf}")
            return None

        df = pd.DataFrame(r['data'],
            columns=['ts','o','h','l','c','vol','v1','v2','conf'])

        df = df[::-1]
        df[['c','h','l']] = df[['c','h','l']].astype(float)

        print(f"📊 {tf} OK")

        return df
    except Exception as e:
        print("Error candles:", e)
        return None

# =========================
# INDICADORES
# =========================
def ema(df, n):
    return df['c'].ewm(span=n).mean()

def atr(df):
    return (df['h'] - df['l']).rolling(14).mean()

# =========================
# DETECTAR MODO
# =========================
def get_mode():

    print("🧠 Analizando mercado...")

    h4 = candles("4H")
    h1 = candles("1H")

    if h4 is None or h1 is None:
        return None

    h4['ema50'], h4['ema200'] = ema(h4,50), ema(h4,200)
    h1['ema50'], h1['ema200'] = ema(h1,50), ema(h1,200)

    if h4['ema50'].iloc[-1] > h4['ema200'].iloc[-1] and h1['ema50'].iloc[-1] > h1['ema200'].iloc[-1]:
        print("📈 LONG MODE")
        return "long"

    elif h4['ema50'].iloc[-1] < h4['ema200'].iloc[-1] and h1['ema50'].iloc[-1] < h1['ema200'].iloc[-1]:
        print("📉 SHORT MODE")
        return "short"

    print("⚖️ NEUTRAL MODE")
    return "neutral"

# =========================
# ORDEN
# =========================
def place_order(side, px, sl, tp):

    print(f"📥 Orden {side} @ {px}")

    body = json.dumps({
        "instId": SYMBOL,
        "tdMode": "isolated",
        "side": side,
        "ordType": "limit",
        "px": str(px),
        "sz": SIZE,
        "lever": "3",
        "slTriggerPx": str(sl),
        "tpTriggerPx": str(tp)
    })

    path = "/api/v5/trade/order"

    r = requests.post(BASE_URL + path,
        headers=headers("POST", path, body),
        data=body)

    print("📡 OKX:", r.json())

# =========================
# GRID ULTRA SCALPING
# =========================
def build_grid(price, atr_val, mode):

    step = atr_val * 0.25  # 🔥 ultra scalping

    print(f"⚙️ Construyendo grid | step: {step}")

    for i in range(1, GRID_LEVELS + 1):

        if mode == "long":

            entry = price - step * i
            place_order(
                "buy",
                entry,
                entry - atr_val * 0.8,
                entry + atr_val * 1.5
            )

        elif mode == "short":

            entry = price + step * i
            place_order(
                "sell",
                entry,
                entry + atr_val * 0.8,
                entry - atr_val * 1.5
            )

        else:

            buy = price - step * i
            sell = price + step * i

            place_order("buy", buy, buy - atr_val, buy + atr_val * 1.5)
            place_order("sell", sell, sell + atr_val, sell - atr_val * 1.5)

# =========================
# RUN
# =========================
def run():

    print("🔍 Escaneando BTC...")

    m1 = candles("1m")

    if m1 is None or len(m1) < 50:
        print("❌ Sin datos 1M")
        return

    price = m1['c'].iloc[-1]

    atr_series = atr(m1)

    if atr_series is None or len(atr_series) < 20:
        print("❌ ATR error")
        return

    atr_val = atr_series.iloc[-1]

    if pd.isna(atr_val) or atr_val == 0:
        print("❌ ATR inválido")
        return

    print(f"💰 Precio: {price} | ATR: {atr_val}")

    mode = get_mode()

    if mode is None:
        print("❌ Sin modo")
        return

    print("🚀 Ejecutando GRID...")

    build_grid(price, atr_val, mode)

# =========================
# LOOP
# =========================
while True:
    try:
        print("\n💀 SNIPER GRID ULTRA ACTIVO...\n")
        run()
        time.sleep(90)
    except Exception as e:
        print("💥 Error:", e)
        time.sleep(30)