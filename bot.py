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
TP_GLOBAL = 0.01   # SOLO TAKE PROFIT

TIMEFRAME = "5m"
MARGIN_MODE = "isolated"

# ========= LOG =========

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

# ========= TIME =========

last_ts = None
last_time = 0

def get_server_time():
    global last_ts, last_time
    if last_ts is None or time.time() - last_time > 5:
        r = requests.get(BASE_URL + "/api/v5/public/time").json()
        last_ts = r["data"][0]["ts"]
        last_time = time.time()
    return last_ts

# ========= AUTH =========

def sign(ts, method, path, body=""):
    msg = f"{ts}{method}{path}{body}"
    return base64.b64encode(
        hmac.new(SECRET_KEY.encode(), msg.encode(), digestmod="sha256").digest()
    ).decode()

def headers(method, path, body=""):
    ts_sec = int(get_server_time()) / 1000
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

def get_pairs():
    r = requests.get(BASE_URL + "/api/v5/market/tickers?instType=SWAP").json()
    df = pd.DataFrame(r["data"])
    df["vol"] = df["vol24h"].astype(float)
    return df.sort_values("vol", ascending=False).head(5)["instId"].tolist()

def get_klines(symbol):
    r = requests.get(f"{BASE_URL}/api/v5/market/candles?instId={symbol}&bar={TIMEFRAME}&limit=100").json()
    df = pd.DataFrame(r["data"])
    df = df.iloc[:, :6]
    df.columns = ["time","open","high","low","close","volume"]
    return df.astype(float)[::-1]

# ========= INDICADORES =========

def ema(df,p):
    return df["close"].ewm(span=p).mean()

def atr(df):
    return (df["high"] - df["low"]).rolling(14).mean()

# ========= IA SCORE =========

def score(df):
    e50 = ema(df,50).iloc[-1]
    e200 = ema(df,200).iloc[-1]
    price = df["close"].iloc[-1]
    momentum = df["close"].pct_change().iloc[-5:].mean()

    s = 0
    if e50 > e200: s += 30
    if price > e50: s += 20
    if momentum > 0: s += 20

    vol = atr(df).iloc[-1] / price
    if vol > 0.005: s += 20

    return s

# ========= BALANCE =========

def get_balance():
    r = requests.get(BASE_URL+"/api/v5/account/balance",
                     headers=headers("GET","/api/v5/account/balance")).json()
    for d in r["data"][0]["details"]:
        if d["ccy"] == "USDT":
            return float(d["eq"])
    return CAPITAL_INICIAL

# ========= POSICIONES =========

def get_positions(symbol):
    r = requests.get(BASE_URL+f"/api/v5/account/positions?instId={symbol}",
                     headers=headers("GET",f"/api/v5/account/positions?instId={symbol}")).json()
    return r.get("data", [])

# ========= CERRAR SOLO EN PROFIT =========

def close_all(symbol):
    log("💰 CERRANDO EN TAKE PROFIT")

    positions = get_positions(symbol)

    for p in positions:
        side = "sell" if float(p["pos"]) > 0 else "buy"

        body = json.dumps({
            "instId": symbol,
            "tdMode": MARGIN_MODE,
            "side": side,
            "ordType": "market",
            "sz": p["pos"]
        })

        requests.post(BASE_URL+"/api/v5/trade/order",
                      headers=headers("POST","/api/v5/trade/order",body),
                      data=body)

# ========= ORDEN =========

def place(symbol, side, price, size):
    body = json.dumps({
        "instId": symbol,
        "tdMode": MARGIN_MODE,
        "side": side,
        "ordType": "limit",
        "px": str(round(price,2)),
        "sz": str(size)
    })

    r = requests.post(BASE_URL+"/api/v5/trade/order",
                      headers=headers("POST","/api/v5/trade/order",body),
                      data=body).json()

    log(f"{symbol} {side} → {r.get('code')}")

# ========= BOT =========

def run():
    log("💰 BOT GRID SOLO TP ACTIVO")

    while True:
        try:
            balance = get_balance()
            pnl = (balance - CAPITAL_INICIAL) / CAPITAL_INICIAL

            log(f"💰 Balance: {balance} | PnL: {round(pnl*100,2)}%")

            # SOLO TAKE PROFIT
            if pnl >= TP_GLOBAL:
                log("🎯 TAKE PROFIT ALCANZADO")
                pares = get_pairs()
                for p in pares:
                    close_all(p)
                time.sleep(10)
                continue

            pares = get_pairs()

            mejor = None
            mejor_score = 0

            for p in pares:
                df = get_klines(p)
                s = score(df)

                if s > mejor_score:
                    mejor_score = s
                    mejor = p

            if mejor_score < 60:
                log("⏳ Sin oportunidad")
                time.sleep(60)
                continue

            if get_positions(mejor):
                log("⏳ Trade activo")
                time.sleep(60)
                continue

            df = get_klines(mejor)
            price = df["close"].iloc[-1]
            atr_val = atr(df).iloc[-1]

            niveles = 5
            paso = (atr_val * 1.5) / niveles

            log(f"🚀 Operando {mejor} SCORE {mejor_score}")

            for i in range(niveles):
                level = price + (i - niveles//2)*paso
                side = "buy" if level < price else "sell"
                place(mejor, side, level, 0.01)

            time.sleep(120)

        except Exception as e:
            log(f"❌ ERROR: {e}")
            time.sleep(30)

# ========= START =========

if __name__ == "__main__":
    run()