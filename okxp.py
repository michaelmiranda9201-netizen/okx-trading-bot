import requests
import time
import hmac
import base64
import json
from datetime import datetime
import pandas as pd

# =========================
# 🔑 CONFIG
# =========================
API_KEY = "db75d70b-f577-40e5-b06c-60b9c87584a7"
SECRET_KEY = "DD0B0C2024162F50F4267C1D59C4AC81"
PASSPHRASE = "WXcv8089@"

BASE_URL = "https://www.okx.com"

CAPITAL = 50
RISK = 0.02
MAX_TRADES = 2
SCORE_THRESHOLD = 70

# =========================
# 🔐 AUTH
# =========================
def headers(method, path, body=""):
    ts = datetime.utcnow().isoformat() + "Z"
    msg = ts + method + path + body
    sign = base64.b64encode(hmac.new(
        SECRET_KEY.encode(), msg.encode(), 'sha256').digest())
    return {
        "OK-ACCESS-KEY": API_KEY,
        "OK-ACCESS-SIGN": sign.decode(),
        "OK-ACCESS-TIMESTAMP": ts,
        "OK-ACCESS-PASSPHRASE": PASSPHRASE,
        "Content-Type": "application/json"
    }

# =========================
# 🔍 OBTENER PARES
# =========================
def get_pairs():
    url = "/api/v5/public/instruments?instType=SWAP"
    r = requests.get(BASE_URL + url).json()
    pairs = []
    for i in r['data']:
        if "USDT" in i['instId']:
            pairs.append(i['instId'])
    return pairs

# =========================
# 📊 DATA
# =========================
def candles(symbol, tf):
    url = f"/api/v5/market/candles?instId={symbol}&bar={tf}&limit=200"
    r = requests.get(BASE_URL + url).json()
    df = pd.DataFrame(r['data'],
        columns=['ts','o','h','l','c','vol','v1','v2','conf'])
    df = df[::-1]
    df[['c','h','l']] = df[['c','h','l']].astype(float)
    return df

# =========================
# 📈 INDICADORES
# =========================
def ema(df, n):
    return df['c'].ewm(span=n).mean()

def atr(df, n=14):
    return (df['h'] - df['l']).rolling(n).mean()

# =========================
# 🧠 SCORE ENGINE
# =========================
def score_pair(symbol):
    try:
        d1 = candles(symbol, "1D")
        h4 = candles(symbol, "4H")
        h1 = candles(symbol, "1H")

        d1['ema50'], d1['ema200'] = ema(d1,50), ema(d1,200)
        h4['ema50'], h4['ema200'] = ema(h4,50), ema(h4,200)
        h1['ema50'], h1['ema200'] = ema(h1,50), ema(h1,200)
        h1['atr'] = atr(h1)

        score = 0

        # 🧭 Tendencia 1D
        if d1['ema50'].iloc[-1] > d1['ema200'].iloc[-1]:
            score += 30
            direction = "buy"
        elif d1['ema50'].iloc[-1] < d1['ema200'].iloc[-1]:
            score += 30
            direction = "sell"
        else:
            return None

        # 🔁 Confirmación 4H
        if direction == "buy" and h4['ema50'].iloc[-1] > h4['ema200'].iloc[-1]:
            score += 25
        elif direction == "sell" and h4['ema50'].iloc[-1] < h4['ema200'].iloc[-1]:
            score += 25

        # 🎯 Setup 1H
        if direction == "buy" and h1['ema50'].iloc[-1] > h1['ema200'].iloc[-1]:
            score += 20
        elif direction == "sell" and h1['ema50'].iloc[-1] < h1['ema200'].iloc[-1]:
            score += 20

        # ⚡ Volatilidad
        atr_val = h1['atr'].iloc[-1]
        if atr_val > h1['c'].iloc[-1] * 0.002:
            score += 15

        # 🚀 Momentum
        diff = abs(h4['ema50'].iloc[-1] - h4['ema200'].iloc[-1])
        if diff / h4['c'].iloc[-1] > 0.005:
            score += 10

        return {
            "symbol": symbol,
            "score": score,
            "direction": direction,
            "price": h1['c'].iloc[-1],
            "atr": atr_val
        }

    except:
        return None

# =========================
# 💣 LEVERAGE
# =========================
def leverage(score):
    if score > 85:
        return 5
    elif score > 75:
        return 3
    return 2

# =========================
# 📦 POSICIONES
# =========================
def positions():
    path = "/api/v5/account/positions"
    r = requests.get(BASE_URL + path, headers=headers("GET", path)).json()
    return [p for p in r['data'] if float(p['pos']) != 0]

# =========================
# 💰 SIZE
# =========================
def size(price, sl):
    risk_amt = CAPITAL * RISK
    dist = abs(price - sl)
    return round(risk_amt / dist, 4)

# =========================
# 🚀 ORDEN
# =========================
def trade(data):
    lev = leverage(data['score'])
    price = data['price']
    atr = data['atr']

    if data['direction'] == "buy":
        sl = price - atr * 1.2
        tp = price + atr * 2.5
    else:
        sl = price + atr * 1.2
        tp = price - atr * 2.5

    sz = size(price, sl)

    body = json.dumps({
        "instId": data['symbol'],
        "tdMode": "isolated",
        "side": data['direction'],
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

    print("TRADE:", data['symbol'], data['score'], r.json())

# =========================
# 🔁 MAIN LOOP
# =========================
while True:
    try:
        pairs = get_pairs()
        results = []

        print(f"Escaneando {len(pairs)} pares...")

        for p in pairs:
            s = score_pair(p)
            if s:
                results.append(s)

        # 🔝 Ordenar por score
        results = sorted(results, key=lambda x: x['score'], reverse=True)

        # 📊 Mostrar top
        for r in results[:5]:
            print(r['symbol'], r['score'])

        # ⚔️ Ejecutar trades
        open_pos = len(positions())

        for r in results:
            if r['score'] >= SCORE_THRESHOLD and open_pos < MAX_TRADES:
                trade(r)
                open_pos += 1

        time.sleep(300)

    except Exception as e:
        print("Error:", e)
        time.sleep(60)