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

CAPITAL_INICIAL = 50
RIESGO = 0.05
TP_GLOBAL = 0.01     # +1%
SL_GLOBAL = -0.02    # -2%

SYMBOL = "BTC-USDT-SWAP"
TIMEFRAME = "5m"

MARGIN_MODE = "isolated"

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
        r = requests.get(url).json()
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
    ts_sec = int(get_server_time_cached()) / 1000
    dt = datetime.fromtimestamp(ts_sec, UTC)
    ts = dt.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'

    return {
        "OK-ACCESS-KEY": API_KEY,
        "OK-ACCESS-SIGN": sign(ts, method, path, body),
        "OK-ACCESS-TIMESTAMP": ts,
        "OK-ACCESS-PASSPHRASE": PASSPHRASE,
        "Content-Type": "application/json"
    }

# ========= BALANCE =========

def get_balance():
    path = "/api/v5/account/balance"
    r = requests.get(BASE_URL + path, headers=headers("GET", path)).json()

    try:
        for acc in r["data"][0]["details"]:
            if acc["ccy"] == "USDT":
                return float(acc["eq"])
    except:
        return CAPITAL_INICIAL

    return CAPITAL_INICIAL

# ========= POSICIONES =========

def get_positions():
    path = f"/api/v5/account/positions?instId={SYMBOL}"
    r = requests.get(BASE_URL + path, headers=headers("GET", path)).json()
    return r.get("data", [])

# ========= CERRAR TODO =========

def close_all():
    log("🚨 CERRANDO TODAS LAS POSICIONES")

    positions = get_positions()

    for p in positions:
        side = "sell" if p["posSide"] == "long" else "buy"

        body = json.dumps({
            "instId": SYMBOL,
            "tdMode": MARGIN_MODE,
            "side": side,
            "ordType": "market",
            "sz": p["pos"]
        })

        requests.post(BASE_URL+"/api/v5/trade/order",
                      headers=headers("POST","/api/v5/trade/order",body),
                      data=body)

# ========= GRID =========

def get_klines():
    url = f"{BASE_URL}/api/v5/market/candles?instId={SYMBOL}&bar={TIMEFRAME}&limit=100"
    data = requests.get(url).json()["data"]

    df = pd.DataFrame(data)
    df.columns = ["time","open","high","low","close","volume","x","y","z"]
    return df.astype(float)[::-1]

def atr(df):
    return (df["high"] - df["low"]).rolling(14).mean()

# ========= ORDEN =========

def place(side, price, size):
    body = json.dumps({
        "instId": SYMBOL,
        "tdMode": MARGIN_MODE,
        "side": side,
        "ordType": "limit",
        "px": str(round(price,2)),
        "sz": str(size)
    })

    requests.post(BASE_URL+"/api/v5/trade/order",
                  headers=headers("POST","/api/v5/trade/order",body),
                  data=body)

# ========= BOT =========

def run():
    log("💰 MODO DINERO REAL ACTIVADO")

    while True:
        try:
            balance = get_balance()
            pnl = (balance - CAPITAL_INICIAL) / CAPITAL_INICIAL

            log(f"💰 Balance: {balance} | PnL: {round(pnl*100,2)}%")

            # TP / SL
            if pnl >= TP_GLOBAL:
                log("🎯 TAKE PROFIT ALCANZADO")
                close_all()
                break

            if pnl <= SL_GLOBAL:
                log("🛑 STOP LOSS ACTIVADO")
                close_all()
                break

            # evitar sobreoperar
            if get_positions():
                log("⏳ Ya hay posición activa")
                time.sleep(60)
                continue

            df = get_klines()
            price = df["close"].iloc[-1]
            atr_val = atr(df).iloc[-1]

            rango = atr_val * 1.5
            niveles = 5
            paso = rango / niveles

            size = 0.01

            log("🚀 NUEVO GRID")

            for i in range(niveles):
                level = price + (i - niveles//2)*paso

                if level < price:
                    place("buy", level, size)
                else:
                    place("sell", level, size)

            time.sleep(120)

        except Exception as e:
            log(f"❌ ERROR: {e}")
            time.sleep(30)

if __name__ == "__main__":
    run()