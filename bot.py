import time
import requests
import numpy as np
import pandas as pd
import hmac, base64, json, os
import websocket
import threading
from datetime import datetime, UTC

# ========= CONFIG =========
API_KEY = os.getenv("db75d70b-f577-40e5-b06c-60b9c87584a7")
SECRET_KEY = os.getenv("DD0B0C2024162F50F4267C1D59C4AC81")
PASSPHRASE = os.getenv("WXcv8089@")

BASE_URL = "https://www.okx.com"

CAPITAL_INICIAL = 50
RIESGO = 0.02
TP_GLOBAL = 0.01
SL_GLOBAL = -0.03

TIMEFRAME = "5m"
MARGIN_MODE = "isolated"

SYMBOLS = ["BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP"]

# ========= LOG =========
def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

# ========= TIME =========
last_ts = None
last_time = 0

def get_server_time():
    global last_ts, last_time
    try:
        if last_ts is None or time.time() - last_time > 5:
            r = requests.get(BASE_URL + "/api/v5/public/time", timeout=5)
            last_ts = int(r.json()["data"][0]["ts"])
            last_time = time.time()
        return last_ts
    except:
        return int(time.time() * 1000)

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

# ========= WEBSOCKET =========
price_data = {}
ws_connected = False

def on_message(ws, message):
    global price_data
    try:
        data = json.loads(message)
        if "data" in data:
            for d in data["data"]:
                if "last" in d:
                    symbol = d["instId"]
                    price_data[symbol] = float(d["last"])
    except:
        pass

def on_open(ws):
    global ws_connected
    ws_connected = True
    log("✅ WebSocket conectado")

    args = [{"channel": "tickers", "instId": s} for s in SYMBOLS]

    ws.send(json.dumps({
        "op": "subscribe",
        "args": args
    }))

def on_error(ws, error):
    log(f"❌ WS Error: {error}")

def on_close(ws, a, b):
    global ws_connected
    ws_connected = False
    log("⚠️ WS desconectado, reconectando...")
    time.sleep(5)
    start_ws()

def start_ws():
    def run():
        ws = websocket.WebSocketApp(
            "wss://ws.okx.com:8443/ws/v5/public",
            on_message=on_message,
            on_open=on_open,
            on_error=on_error,
            on_close=on_close
        )
        ws.run_forever(ping_interval=20, ping_timeout=10)

    t = threading.Thread(target=run)
    t.daemon = True
    t.start()

# ========= MARKET =========
def get_klines(symbol):
    try:
        r = requests.get(f"{BASE_URL}/api/v5/market/candles?instId={symbol}&bar={TIMEFRAME}&limit=100", timeout=5)
        df = pd.DataFrame(r.json()["data"])
        df = df.iloc[:, :6]
        df.columns = ["time","open","high","low","close","volume"]
        return df.astype(float)[::-1]
    except:
        return None

# ========= IA =========
def ai_signal(df):
    try:
        close = df["close"]

        ema50 = close.ewm(span=50).mean().iloc[-1]
        ema200 = close.ewm(span=200).mean().iloc[-1]

        momentum = close.pct_change().iloc[-10:].mean()
        volatility = df["high"].iloc[-1] - df["low"].iloc[-1]

        prob_buy = 0
        prob_sell = 0

        if ema50 > ema200:
            prob_buy += 0.4
        else:
            prob_sell += 0.4

        if momentum > 0:
            prob_buy += 0.3
        else:
            prob_sell += 0.3

        if volatility > close.iloc[-1] * 0.003:
            prob_buy += 0.1
            prob_sell += 0.1

        if close.iloc[-1] > close.iloc[-3]:
            prob_buy += 0.2
        else:
            prob_sell += 0.2

        if prob_buy > 0.6:
            return "buy"
        elif prob_sell > 0.6:
            return "sell"
        else:
            return None

    except:
        return None

# ========= MARTINGALA =========
martingale_step = 0
MAX_MARTINGALA = 3

def get_size(balance, price):
    global martingale_step
    base = (balance * RIESGO) / price
    multiplier = 1.5 ** martingale_step
    return round(base * multiplier, 3)

def update_martingale(win):
    global martingale_step
    if win:
        martingale_step = 0
    else:
        if martingale_step < MAX_MARTINGALA:
            martingale_step += 1

# ========= BALANCE =========
def get_balance():
    try:
        r = requests.get(BASE_URL+"/api/v5/account/balance",
                         headers=headers("GET","/api/v5/account/balance"), timeout=5)
        for d in r.json()["data"][0]["details"]:
            if d["ccy"] == "USDT":
                return float(d["eq"])
    except:
        pass
    return CAPITAL_INICIAL

# ========= POSICIONES =========
def get_positions(symbol):
    try:
        r = requests.get(BASE_URL+f"/api/v5/account/positions?instId={symbol}",
                         headers=headers("GET",f"/api/v5/account/positions?instId={symbol}"),
                         timeout=5)
        return r.json().get("data", [])
    except:
        return []

# ========= ORDEN =========
def place(symbol, side, price, balance):
    size = get_size(balance, price)

    body = json.dumps({
        "instId": symbol,
        "tdMode": MARGIN_MODE,
        "side": side,
        "ordType": "market",
        "sz": str(size)
    })

    r = requests.post(BASE_URL+"/api/v5/trade/order",
                      headers=headers("POST","/api/v5/trade/order",body),
                      data=body, timeout=5).json()

    log(f"{symbol} {side} → {r.get('code')} size:{size}")

# ========= CERRAR =========
def close_all(symbol):
    positions = get_positions(symbol)
    for p in positions:
        pos = float(p["pos"])
        side = "sell" if pos > 0 else "buy"

        body = json.dumps({
            "instId": symbol,
            "tdMode": MARGIN_MODE,
            "side": side,
            "ordType": "market",
            "sz": str(abs(pos))
        })

        requests.post(BASE_URL+"/api/v5/trade/order",
                      headers=headers("POST","/api/v5/trade/order",body),
                      data=body, timeout=5)

# ========= BOT =========
def run():
    log("🚀 BOT IA PRO (FIXED WS)")

    start_ws()

    while True:
        try:
            balance = get_balance()
            pnl = (balance - CAPITAL_INICIAL) / CAPITAL_INICIAL

            log(f"💰 Balance: {balance} | PnL: {round(pnl*100,2)}%")

            if pnl >= TP_GLOBAL:
                log("🎯 TAKE PROFIT")
                for s in SYMBOLS:
                    close_all(s)
                time.sleep(30)
                continue

            if pnl <= SL_GLOBAL:
                log("🛑 STOP LOSS")
                for s in SYMBOLS:
                    close_all(s)
                time.sleep(60)
                continue

            for symbol in SYMBOLS:

                df = get_klines(symbol)
                if df is None:
                    continue

                signal = ai_signal(df)
                if not signal:
                    continue

                if len(get_positions(symbol)) > 0:
                    continue

                price = price_data.get(symbol)

                # 🔥 FALLBACK SI WS FALLA
                if not price:
                    log(f"⚠️ WS fallback {symbol}")
                    price = df["close"].iloc[-1]

                log(f"🔥 {symbol} → {signal}")

                place(symbol, signal, price, balance)

                break

            time.sleep(60)

        except Exception as e:
            log(f"❌ ERROR: {e}")
            time.sleep(30)

# ========= START =========
if __name__ == "__main__":
    run()