import os
import requests
import numpy as np
import time
import okx.Trade as Trade
import okx.Account as Account

# ==========================================
# CONFIGURACION
# ==========================================

API_KEY = os.getenv("db75d70b-f577-40e5-b06c-60b9c87584a7")
SECRET_KEY = os.getenv("DD0B0C2024162F50F4267C1D59C4AC81")
PASSPHRASE = os.getenv("WXcv8089@")

tradeAPI = Trade.TradeAPI(API_KEY, SECRET_KEY, PASSPHRASE, False, "0")
accountAPI = Account.AccountAPI(API_KEY, SECRET_KEY, PASSPHRASE, False, "0")

BASE_URL = "https://www.okx.com"

MAX_OPERACIONES = 2
SCORE_MINIMO = 85
RIESGO = 0.08

operaciones_abiertas = {}

# ==========================================
# LOG
# ==========================================

def log(msg):
    print(f"[BOT] {msg}")

# ==========================================
# BALANCE
# ==========================================

def obtener_balance():

    try:
        data = accountAPI.get_account_balance()

        for d in data['data'][0]['details']:
            if d['ccy'] == 'USDT':
                return float(d['availBal'])

    except:
        pass

    return 0

# ==========================================
# PARES USDT
# ==========================================

def obtener_pares():

    url = BASE_URL + "/api/v5/public/instruments?instType=SWAP"

    r = requests.get(url).json()

    pares = []

    for i in r["data"]:
        if "USDT" in i["instId"]:
            pares.append(i["instId"])

    return pares

# ==========================================
# VELAS
# ==========================================

def obtener_velas(par):

    url = f"{BASE_URL}/api/v5/market/candles?instId={par}&bar=1H&limit=200"

    r = requests.get(url).json()

    data = r["data"]

    closes = [float(v[4]) for v in data]
    highs = [float(v[2]) for v in data]
    lows = [float(v[3]) for v in data]

    return closes, highs, lows

# ==========================================
# EMA
# ==========================================

def ema(data, period):

    data = np.array(data)

    weights = np.exp(np.linspace(-1.,0.,period))
    weights /= weights.sum()

    a = np.convolve(data,weights,mode='full')[:len(data)]
    a[:period] = a[period]

    return a

# ==========================================
# ATR
# ==========================================

def calcular_atr(highs,lows,closes):

    trs = []

    for i in range(1,len(highs)):

        tr = max(
            highs[i]-lows[i],
            abs(highs[i]-closes[i-1]),
            abs(lows[i]-closes[i-1])
        )

        trs.append(tr)

    return np.mean(trs[-14:])

# ==========================================
# ESTRUCTURA
# ==========================================

def estructura(highs,lows):

    maximo = max(highs[-20:])
    minimo = min(lows[-20:])

    if highs[-1] > maximo:
        return "LONG"

    if lows[-1] < minimo:
        return "SHORT"

    return "RANGO"

# ==========================================
# ANALISIS
# ==========================================

def analizar(closes,highs,lows):

    ema50 = ema(closes,50)[-1]
    ema200 = ema(closes,200)[-1]

    close = closes[-1]

    score = 0
    tendencia = "NEUTRAL"

    if ema50 > ema200:
        score += 40
        tendencia = "LONG"

    if ema50 < ema200:
        score += 40
        tendencia = "SHORT"

    if close > ema50:
        score += 20

    bos = estructura(highs,lows)

    if bos == tendencia:
        score += 25

    atr = calcular_atr(highs,lows,closes)

    return score,tendencia,atr

# ==========================================
# PRECIO
# ==========================================

def precio_actual(par):

    url = f"{BASE_URL}/api/v5/market/ticker?instId={par}"

    r = requests.get(url).json()

    return float(r["data"][0]["last"])

# ==========================================
# ABRIR TRADE
# ==========================================

def abrir_trade(par,tendencia,atr):

    balance = obtener_balance()

    tamaño = round(balance * RIESGO,2)

    lado = "buy" if tendencia == "LONG" else "sell"

    log(f"🚀 Ejecutando trade {par} {tendencia}")
    log(f"Tamaño USDT {tamaño}")

    try:

        orden = tradeAPI.place_order(
            instId=par,
            tdMode="isolated",
            side=lado,
            ordType="market",
            sz=str(tamaño)
        )

        log(f"Orden enviada {orden}")

        operaciones_abiertas[par] = {

            "lado":tendencia,
            "atr":atr,
            "sl":0
        }

    except Exception as e:

        log(f"Error trade {e}")

# ==========================================
# TRAILING
# ==========================================

def trailing():

    for par in operaciones_abiertas:

        try:

            precio = precio_actual(par)

            trade = operaciones_abiertas[par]

            if trade["lado"] == "LONG":

                nuevo_sl = precio - trade["atr"]

                if nuevo_sl > trade["sl"]:

                    trade["sl"] = nuevo_sl

                    log(f"Trailing actualizado {par}")

            if trade["lado"] == "SHORT":

                nuevo_sl = precio + trade["atr"]

                if nuevo_sl < trade["sl"]:

                    trade["sl"] = nuevo_sl

                    log(f"Trailing actualizado {par}")

        except:
            pass

# ==========================================
# ESCANEO
# ==========================================

def escanear():

    pares = obtener_pares()

    mercados = []

    log(f"Escaneando {len(pares)} pares")

    for par in pares:

        try:

            closes,highs,lows = obtener_velas(par)

            score,tendencia,atr = analizar(closes,highs,lows)

            mercados.append({

                "par":par,
                "score":score,
                "tendencia":tendencia,
                "atr":atr
            })

        except:
            pass

    mercados = sorted(mercados,key=lambda x:x["atr"],reverse=True)

    mercados = mercados[:25]

    mercados = sorted(mercados,key=lambda x:x["score"],reverse=True)

    log("TOP oportunidades")

    for m in mercados[:10]:

        log(f"{m['par']} score {m['score']} {m['tendencia']}")

    for m in mercados:

        if len(operaciones_abiertas) >= MAX_OPERACIONES:

            log("Máximo operaciones alcanzado")

            return

        if m["score"] >= SCORE_MINIMO:

            abrir_trade(m["par"],m["tendencia"],m["atr"])

# ==========================================
# LOOP
# ==========================================

log("BOT INICIADO")

while True:

    try:

        escanear()

        trailing()

        log("Esperando 5 minutos")

        time.sleep(300)

    except Exception as e:

        log(f"Error controlado {e}")

        time.sleep(60)