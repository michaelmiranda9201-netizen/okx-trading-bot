import time
import requests
import numpy as np
import pandas as pd
import hmac, base64, json
from datetime import datetime

# ========= CONFIG =========

API_KEY = "db75d70b-f577-40e5-b06c-60b9c87584a7"
SECRET_KEY = "DD0B0C2024162F50F4267C1D59C4AC81"
PASSPHRASE = "WXcv8089@"

BASE_URL = "https://www.okx.com"

CAPITAL = 50
RIESGO = 0.02
TIMEFRAME = "5m"

MARGIN_MODE = "isolated"
ATR_PERIOD = 14

TP_GLOBAL = 0.015  # 1.5%

# =========================

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

# ========= AUTH =========

def sign(ts, method, path, body=""):
    msg = f"{ts}{method}{path}{body}"
    return base64.b64encode(hmac.new(SECRET_KEY.encode(), msg.encode(), digestmod="sha256").digest()).decode()

def headers(method, path, body=""):
    ts = datetime.utcnow().isoformat() + "Z"
    return {
        "OK-ACCESS-KEY": API_KEY,
        "OK-ACCESS-SIGN": sign(ts, method, path, body),
        "OK-ACCESS-TIMESTAMP": ts,
        "OK-ACCESS-PASSPHRASE": PASSPHRASE,
        "Content-Type": "application/json"
    }

# ========= MARKET =========

def get_pairs():
    url = f"{BASE_URL}/api/v5/market/tickers?instType=SWAP"
    data = requests.get(url).json()["data"]
    usdt = [p for p in data if "USDT" in p["instId"]]
    df = pd.DataFrame(usdt)
    df["vol"] = df["vol24h"].astype(float)
    return df.sort_values("vol", ascending=False).head(10)["instId"].tolist()

def get_klines(symbol):
    url = f"{BASE_URL}/api/v5/market/candles?instId={symbol}&bar={TIMEFRAME}&limit=100"
    data = requests.get(url).json()["data"]
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
    if vol > 0.005: s += 15

    return s

# ========= MANIPULACION =========

def fake_breakout(df):
    last = df.iloc[-1]
    body = abs(last["close"] - last["open"])
    wick = last["high"] - last["low"]

    return wick > body * 3

# ========= GRID =========

def grid(price, atr_val):
    niveles = 7 if atr_val/price > 0.005 else 5
    rango = atr_val * 1.5
    paso = rango / niveles
    return [price + (i - niveles//2)*paso for i in range(niveles)]

# ========= ORDENES =========

def place(symbol, side, price, size):
    path = "/api/v5/trade/order"
    body = json.dumps({
        "instId": symbol,
        "tdMode": MARGIN_MODE,
        "side": side,
        "ordType": "limit",
        "px": str(round(price,2)),
        "sz": str(size)
    })
    requests.post(BASE_URL+path, headers=headers("POST",path,body), data=body)

def cancel_all(symbol):
    path = f"/api/v5/trade/orders-pending?instId={symbol}"
    r = requests.get(BASE_URL+path, headers=headers("GET",path)).json()

    for o in r.get("data", []):
        body = json.dumps({"instId":symbol,"ordId":o["ordId"]})
        requests.post(BASE_URL+"/api/v5/trade/cancel-order",
                      headers=headers("POST","/api/v5/trade/cancel-order",body),
                      data=body)

# ========= TP GLOBAL =========

balance_inicial = CAPITAL

def check_tp(balance):
    return (balance - balance_inicial) / balance_inicial >= TP_GLOBAL

# ========= BOT =========

def run():
    log("😈 MODO DIOS ACTIVADO")

    activo = None
    niveles = None

    while True:
        try:
            pares = get_pairs()

            mejor = None
            best_score = 0

            for p in pares:
                df = get_klines(p)

                if fake_breakout(df):
                    continue

                s = score(df)

                if s > best_score:
                    best_score = s
                    mejor = p

            if best_score < 70:
                log("❌ Sin oportunidades fuertes")
                time.sleep(60)
                continue

            df = get_klines(mejor)
            price = df["close"].iloc[-1]
            atr_val = atr(df).iloc[-1]

            if activo != mejor or niveles is None or price < min(niveles) or price > max(niveles):
                log(f"🚀 {mejor} SCORE {best_score}")
                cancel_all(mejor)

                niveles = grid(price, atr_val)
                size = round((CAPITAL*RIESGO)/price,4)

                for n in niveles:
                    if n < price:
                        place(mejor,"buy",n,size)
                    else:
                        place(mejor,"sell",n,size)

                activo = mejor

            log(f"⏳ {mejor} trabajando...")

            time.sleep(60)

        except Exception as e:
            log(f"❌ Error: {e}")
            time.sleep(30)

if __name__ == "__main__":
    run()