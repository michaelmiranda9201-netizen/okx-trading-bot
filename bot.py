import time
import hmac
import base64
import hashlib
import requests
import pandas as pd
import numpy as np
from datetime import datetime

API_KEY = "db75d70b-f577-40e5-b06c-60b9c87584a7"
SECRET_KEY = "DD0B0C2024162F50F4267C1D59C4AC81"
PASSPHRASE = "WXcv8089@"

BASE = "https://www.okx.com"

TRADE_SIZE = "1"
MAX_TRADES = 2

open_positions = {}

# firma API

def sign(timestamp, method, request_path, body):

    message = str(timestamp) + method + request_path + body
    mac = hmac.new(bytes(SECRET_KEY, encoding='utf8'), bytes(message, encoding='utf-8'), hashlib.sha256)
    d = mac.digest()

    return base64.b64encode(d)

# headers API

def headers(method, path, body=""):

    timestamp = datetime.utcnow().isoformat("T", "milliseconds") + "Z"

    signature = sign(timestamp, method, path, body)

    return {
        "OK-ACCESS-KEY": API_KEY,
        "OK-ACCESS-SIGN": signature,
        "OK-ACCESS-TIMESTAMP": timestamp,
        "OK-ACCESS-PASSPHRASE": PASSPHRASE,
        "Content-Type": "application/json"
    }

# ejecutar orden

def place_order(symbol, side):

    path = "/api/v5/trade/order"

    url = BASE + path

    body = {
        "instId": symbol,
        "tdMode": "isolated",
        "side": side,
        "ordType": "market",
        "sz": TRADE_SIZE
    }

    r = requests.post(url, json=body, headers=headers("POST", path, str(body)))

    print("ORDER:", r.text)

# obtener pares

def get_pairs():

    url = BASE + "/api/v5/public/instruments?instType=SWAP"

    r = requests.get(url).json()

    pairs = []

    for p in r["data"]:

        if "USDT" in p["instId"]:

            pairs.append(p["instId"])

    return pairs

# velas

def get_candles(symbol):

    url = f"{BASE}/api/v5/market/candles?instId={symbol}&bar=1m&limit=120"

    r = requests.get(url).json()

    df = pd.DataFrame(r["data"])

    df = df.iloc[::-1]

    df[1] = df[1].astype(float)
    df[2] = df[2].astype(float)
    df[3] = df[3].astype(float)
    df[4] = df[4].astype(float)
    df[5] = df[5].astype(float)

    return df

# EMA

def ema(series,p):

    return series.ewm(span=p).mean()

# ATR

def atr(df):

    tr = abs(df[2] - df[3])

    return tr.rolling(14).mean().iloc[-1]

# score

def probability_score(df):

    score = 0

    ema50 = df["ema50"].iloc[-1]
    ema200 = df["ema200"].iloc[-1]

    volume = df[5]

    vol_avg = volume.rolling(20).mean().iloc[-1]

    if ema50 > ema200:
        score += 40

    if ema50 < ema200:
        score += 40

    if volume.iloc[-1] > vol_avg:
        score += 20

    if abs(ema50-ema200) > df[4].iloc[-1]*0.001:
        score += 20

    return score

# abrir trade

def trade(symbol, side):

    if len(open_positions) >= MAX_TRADES:
        return

    if symbol in open_positions:
        return

    print("EXECUTING TRADE:", symbol, side)

    place_order(symbol, side)

    open_positions[symbol] = side

# escaneo

def scan_market():

    pairs = get_pairs()

    volatility = []

    for p in pairs:

        try:

            df = get_candles(p)

            v = atr(df)

            volatility.append((p,v))

        except:
            pass

    volatility.sort(key=lambda x: x[1],reverse=True)

    top_pairs = volatility[:25]

    for symbol,_ in top_pairs:

        try:

            df = get_candles(symbol)

            df["ema50"] = ema(df[4],50)
            df["ema200"] = ema(df[4],200)

            score = probability_score(df)

            print(symbol,"score:",score)

            if score < 85:
                continue

            if df["ema50"].iloc[-1] > df["ema200"].iloc[-1]:

                trade(symbol,"buy")

            elif df["ema50"].iloc[-1] < df["ema200"].iloc[-1]:

                trade(symbol,"sell")

        except:
            pass

# loop

while True:

    print("Scanning market...")

    scan_market()

    time.sleep(180)