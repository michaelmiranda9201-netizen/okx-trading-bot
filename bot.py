import time
import requests
import numpy as np
import pandas as pd
import hmac, base64, json
from datetime import datetime, UTC

# ========= CONFIG =========

API_KEY = "db75d70b-f577-40e5-b06c-60b9c87584a7"
SECRET_KEY = "DD0B0C2024162F50F4267C1D59C4AC81"
PASSPHRASE = "WXcv8089@"

BASE_URL = "https://www.okx.com"

CAPITAL = 50
RIESGO = 0.05
TIMEFRAME = "5m"

MARGIN_MODE = "isolated"
ATR_PERIOD = 14

# ========= LOG =========

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

# ========= TIME =========

last_ts = None
last_time = 0

def get_server_time_cached():
    global last_ts, last_time
    now = time.time()

    if last_ts is None or now - last_time > 5:
        url = "https://www.okx.com/api/v5/public/time"
        r = requests.get(url, timeout=5).json()
        last_ts = r["data"][0]["ts"]
        last_time = now

    return last_ts

# ========= AUTH =========

def sign(ts, method, path, body=""):
    msg = f"{ts}{method}{path}{body}"
    return base64.b64encode(
        hmac.new(SECRET_KEY.encode(), msg.encode(), digestmod="sha256").digest()
    ).decode()

def headers(method, path, body=""):
    server_ts = get_server_time_cached()

    ts_sec = int(server_ts) / 1000
    dt = datetime.fromtimestamp(ts_sec, UTC)

    ts = dt.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'

    return {
        "OK-ACCESS-KEY": API_KEY,
        "OK-ACCESS-SIGN": sign(ts, method, path, body),
        "OK-ACCESS-TIMESTAMP": ts,
        "OK-ACCESS-PASSPHRASE": PASSPHRASE,
        "Content-Type": "application/json"
    }

# ========= MARKET =========

def get_klines(symbol):
    url = f"{BASE_URL}/api/v5/market/candles?instId={symbol}&bar={TIMEFRAME}&limit=100"
    data = requests.get(url, timeout=10).json()["data"]

    df = pd.DataFrame(data)
    df = df.iloc[:, :6]
    df.columns = ["time","open","high","low","close","volume"]

    return df.astype(float)[::-1]

# ========= INDICADORES =========

def ema(df,p): return df["close"].ewm(span=p).mean()

def atr(df):
    hl = df["high"] - df["low"]
    hc = abs(df["high"] - df["close"].shift())
    lc = abs(df["low"] - df["close"].shift())
    return pd.Series(np.maximum(hl, np.maximum(hc, lc))).rolling(ATR_PERIOD).mean()

# ========= PRECIO =========

def format_price(price):
    if price > 100:
        return round(price, 2)
    elif price > 1:
        return round(price, 3)
    elif price > 0.01:
        return round(price, 4)
    else:
        return round(price, 6)

# ========= LOT SIZE =========

def get_lot_size(symbol):
    url = f"{BASE_URL}/api/v5/public/instruments?instType=SWAP"
    data = requests.get(url, timeout=10).json()["data"]

    for inst in data:
        if inst["instId"] == symbol:
            return float(inst["lotSz"])

    return 0.001

def adjust_size(size, lot_size):
    return max(lot_size, round(size / lot_size) * lot_size)

# ========= ORDEN =========

def place(symbol, side, price, size):
    try:
        if price <= 0:
            return

        px = format_price(price)
        posSide = "long" if side == "buy" else "short"

        body = json.dumps({
            "instId": symbol,
            "tdMode": MARGIN_MODE,
            "side": side,
            "posSide": posSide,
            "ordType": "limit",
            "px": str(px),
            "sz": str(size)
        })

        r = requests.post(
            BASE_URL + "/api/v5/trade/order",
            headers=headers("POST","/api/v5/trade/order",body),
            data=body,
            timeout=10
        ).json()

        if r.get("code") != "0":
            log(f"❌ Error orden: {r}")
        else:
            log(f"✅ {symbol} {side.upper()} @ {px} size:{size}")

    except Exception as e:
        log(f"❌ Exception orden: {e}")

# ========= BOT =========

def run():
    symbol = "BTC-USDT-SWAP"

    while True:
        try:
            df = get_klines(symbol)

            price = df["close"].iloc[-1]
            atr_val = atr(df).iloc[-1]

            if np.isnan(atr_val):
                log("⚠️ ATR inválido")
                time.sleep(30)
                continue

            niveles = 5
            rango = atr_val * 1.5
            paso = rango / niveles

            grid = [price + (i - niveles//2)*paso for i in range(niveles)]

            lot_size = get_lot_size(symbol)

            raw_size = (CAPITAL * RIESGO) / price
            size = adjust_size(raw_size, lot_size)

            log(f"📦 Size ajustado: {size} | Lot: {lot_size}")
            log("🚀 Ejecutando GRID REAL")

            for n in grid:
                if n < price:
                    place(symbol, "buy", n, size)
                else:
                    place(symbol, "sell", n, size)

            time.sleep(120)

        except Exception as e:
            log(f"❌ ERROR GENERAL: {e}")
            time.sleep(30)

# ========= START =========

if __name__ == "__main__":
    run()