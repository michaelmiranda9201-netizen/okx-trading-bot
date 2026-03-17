import os
import time
import json
import hmac
import base64
import hashlib
import requests
import numpy as np
from datetime import datetime

BASE_URL = "https://www.okx.com"

API_KEY = os.getenv("db75d70b-f577-40e5-b06c-60b9c87584a7")
SECRET_KEY = os.getenv("DD0B0C2024162F50F4267C1D59C4AC81")
PASSPHRASE = os.getenv("WXcv8089@")

MAX_OPERACIONES = 2
SCORE_MINIMO = 85
RIESGO = 0.05

operaciones_abiertas = {}

# =========================
# LOG
# =========================

def log(msg):
    print(f"[PRO BOT] {msg}")

# =========================
# FIRMA
# =========================

def firma(timestamp, method, path, body=""):
    mensaje = f"{timestamp}{method}{path}{body}"
    mac = hmac.new(SECRET_KEY.encode(), mensaje.encode(), hashlib.sha256)
    return base64.b64encode(mac.digest()).decode()

def headers(method, path, body=""):
    timestamp = datetime.utcnow().isoformat(timespec='milliseconds') + "Z"
    sign = firma(timestamp, method, path, body)

    return {
        "OK-ACCESS-KEY": API_KEY,
        "OK-ACCESS-SIGN": sign,
        "OK-ACCESS-TIMESTAMP": timestamp,
        "OK-ACCESS-PASSPHRASE": PASSPHRASE,
        "Content-Type": "application/json"
    }

# =========================
# VELAS 5M
# =========================

def velas(par):
    url = f"{BASE_URL}/api/v5/market/candles?instId={par}&bar=5m&limit=100"
    data = requests.get(url).json()["data"]

    closes = [float(v[4]) for v in data]
    highs = [float(v[2]) for v in data]
    lows = [float(v[3]) for v in data]
    opens = [float(v[1]) for v in data]

    return closes, highs, lows, opens

# =========================
# EMA
# =========================

def ema(data, period):
    data = np.array(data)
    weights = np.exp(np.linspace(-1.,0.,period))
    weights /= weights.sum()
    a = np.convolve(data,weights,mode='full')[:len(data)]
    a[:period] = a[period]
    return a

# =========================
# FILTRO WICK (ANTI MANIPULACION)
# =========================

def wick_fuerte(open_, close, high, low):

    cuerpo = abs(close - open_)
    mecha = (high - low)

    if cuerpo == 0:
        return True

    ratio = mecha / cuerpo

    return ratio > 2  # si hay mucha mecha = manipulación

# =========================
# BREAKOUT REAL
# =========================

def breakout_real(highs, lows, closes):

    resistencia = max(highs[-15:-1])
    soporte = min(lows[-15:-1])

    if closes[-1] > resistencia:
        return "LONG"

    if closes[-1] < soporte:
        return "SHORT"

    return "NONE"

# =========================
# IMPULSO
# =========================

def impulso(closes):
    return closes[-1] > closes[-3]

# =========================
# ANALISIS PRO
# =========================

def analizar(closes, highs, lows, opens):

    ema50 = ema(closes,50)[-1]
    ema200 = ema(closes,200)[-1]

    score = 0
    tendencia = "NEUTRAL"

    if ema50 > ema200:
        score += 30
        tendencia = "LONG"

    if ema50 < ema200:
        score += 30
        tendencia = "SHORT"

    # Confirmación vela
    if closes[-1] > opens[-1]:
        score += 15

    # Evitar manipulación
    if not wick_fuerte(opens[-1], closes[-1], highs[-1], lows[-1]):
        score += 20

    # Breakout real
    bo = breakout_real(highs, lows, closes)

    if bo == tendencia:
        score += 25

    # Impulso
    if impulso(closes):
        score += 10

    return score, tendencia

# =========================
# ABRIR TRADE
# =========================

def abrir_trade(par, tendencia):

    size = 3  # fijo para cuenta pequeña

    side = "buy" if tendencia == "LONG" else "sell"

    path = "/api/v5/trade/order"

    body = json.dumps({
        "instId": par,
        "tdMode": "isolated",
        "side": side,
        "ordType": "market",
        "sz": str(size)
    })

    r = requests.post(
        BASE_URL + path,
        headers=headers("POST", path, body),
        data=body
    )

    log(f"🚀 TRADE REAL {par} {tendencia}")
    log(r.json())

# =========================
# ESCANEO
# =========================

def escanear():

    pares = requests.get(BASE_URL + "/api/v5/public/instruments?instType=SWAP").json()["data"]

    lista = [p["instId"] for p in pares if "USDT" in p["instId"]]

    for par in lista:

        try:

            closes, highs, lows, opens = velas(par)

            score, tendencia = analizar(closes, highs, lows, opens)

            if score >= SCORE_MINIMO:

                log(f"{par} SCORE {score} {tendencia}")

                abrir_trade(par, tendencia)

        except:
            pass

# =========================
# LOOP
# =========================

log("BOT NIVEL 8 PRO INICIADO")

while True:

    try:

        escanear()

        log("Esperando 2 minutos...")

        time.sleep(120)

    except Exception as e:

        log(f"Error {e}")

        time.sleep(60)