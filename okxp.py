import requests
import time
import hmac
import base64
import json
import os
from datetime import datetime
import pandas as pd

# =========================
# 🔑 VARIABLES DE ENTORNO
# =========================
API_KEY = os.getenv("db75d70b-f577-40e5-b06c-60b9c87584a7")
SECRET_KEY = os.getenv("DD0B0C2024162F50F4267C1D59C4AC81")
PASSPHRASE = os.getenv("WXcv8089@")

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
# 🔍 OBTENER PARES
# =========================
def get_pairs():
    try:
        url = "/api/v5/public/instruments?instType=SWAP"
        r = requests.get(BASE_URL + url).json()
        return [i['instId'] for i in r['data'] if "USDT" in i['instId']]
    except:
        return []

# =========================
# 📊 DATA
# =========================
def candles(symbol, tf):
    url = f"/api/v5/market/candles?instId={symbol}&bar={tf}&limit=200"
    r = requests.get(BASE_URL + url).json()

    if 'data' not in r:
        return None

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

        if d1 is None or h4 is None or h1 is None:
            return None

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

        # 🎯 Entrada 1H
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

    except Exception as e:
        print(f"Error en {symbol}: {e}")
        return None

# =========================
# 💣 APALANCAMIENTO
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
    try:
        path = "/api/v5/account/positions"
        r = requests.get(BASE_URL + path, headers=headers("GET", path)).json()
        return [p for p in r.get('data', []) if float(p.get('pos', 0)) != 0]
    except:
        return []

# =========================
# 💰 SIZE DINÁMICO
# =========================
def size(price, sl):
    risk_amt = CAPITAL * RISK
    dist = abs(price - sl)
    if dist == 0:
        return 0
    return round(risk_amt / dist, 4)

# =========================
# 🚀 ORDEN
# =========================
def trade(data):
    lev = leverage(data['score'])
    price = data['price']
    atr_val = data['atr']

    if data['direction'] == "buy":
        sl = price - atr_val * 1.2
        tp = price + atr_val * 2.5
    else:
        sl = price + atr_val * 1.2
        tp = price - atr_val * 2.5

    sz = size(price, sl)

    if sz <= 0:
        print("Size inválido")
        return

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

    try:
        r = requests.post(BASE_URL + path,
            headers=headers("POST", path, body),
            data=body)

        print(f"🚀 TRADE {data['symbol']} | Score: {data['score']} | {r.json()}")

    except Exception as e:
        print("Error al ejecutar orden:", e)

# =========================
# 🔁 LOOP PRINCIPAL
# =========================
while True:
    try:
        pairs = get_pairs()
        results = []

        print(f"\n🔍 Escaneando {len(pairs)} pares...")

        for p in pairs:
            s = score_pair(p)
            if s:
                results.append(s)
            time.sleep(0.2)  # anti rate limit

        results = sorted(results, key=lambda x: x['score'], reverse=True)

        print("\n🏆 TOP OPORTUNIDADES:")
        for r in results[:5]:
            print(f"{r['symbol']} | Score: {r['score']} | {r['direction']}")

        open_pos = len(positions())

        for r in results:
            if r['score'] >= SCORE_THRESHOLD and open_pos < MAX_TRADES:
                trade(r)
                open_pos += 1

        print("⏳ Esperando siguiente ciclo...\n")
        time.sleep(300)

    except Exception as e:
        print("💥 Error general:", e)
        time.sleep(60)