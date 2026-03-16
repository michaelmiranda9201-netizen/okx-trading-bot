import time
import requests
import pandas as pd
import numpy as np
import okx.Trade as Trade

API_KEY = "db75d70b-f577-40e5-b06c-60b9c87584a7"
SECRET_KEY = "DD0B0C2024162F50F4267C1D59C4AC81"
PASSPHRASE = "WXcv8089@"

tradeAPI = Trade.TradeAPI(API_KEY, SECRET_KEY, PASSPHRASE, False, "0")

BASE = "https://www.okx.com"

TRADE_SIZE = "1"
MAX_TRADES = 2

open_positions = {}

# obtener todos los pares swap

def get_pairs():

    url = f"{BASE}/api/v5/public/instruments?instType=SWAP"

    r = requests.get(url).json()

    pairs = []

    for p in r["data"]:

        if "USDT" in p["instId"]:
            pairs.append(p["instId"])

    return pairs


# obtener velas

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


# score del trade

def probability_score(df):

    score = 0

    ema50 = df["ema50"].iloc[-1]
    ema200 = df["ema200"].iloc[-1]

    price = df[4].iloc[-1]

    volume = df[5]

    vol_avg = volume.rolling(20).mean().iloc[-1]

    if ema50 > ema200:
        score += 40

    if ema50 < ema200:
        score += 40

    if volume.iloc[-1] > vol_avg:
        score += 25

    if abs(ema50-ema200) > price*0.001:
        score += 25

    return score


# ejecutar trade

def place_trade(symbol, side, price, atr_value):

    if len(open_positions) >= MAX_TRADES:
        return

    if symbol in open_positions:
        return

    if side == "buy":

        sl = price - atr_value
        tp = price + atr_value*2

    else:

        sl = price + atr_value
        tp = price - atr_value*2

    print("TRADE:",symbol,side)

    tradeAPI.place_order(
        instId=symbol,
        tdMode="isolated",
        side=side,
        ordType="market",
        sz=TRADE_SIZE
    )

    print("SL:",sl,"TP:",tp)

    open_positions[symbol] = side


# escanear mercado

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

            price = df[4].iloc[-1]

            v = atr(df)

            score = probability_score(df)

            print(symbol,"score:",score)

            if score < 85:
                continue

            if df["ema50"].iloc[-1] > df["ema200"].iloc[-1]:

                place_trade(symbol,"buy",price,v)

            elif df["ema50"].iloc[-1] < df["ema200"].iloc[-1]:

                place_trade(symbol,"sell",price,v)

        except:

            pass


# loop principal

while True:

    print("Escaneando mercado...")

    scan_market()

    time.sleep(180)