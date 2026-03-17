import time, json, os, hmac, base64, threading, traceback
import requests
import pandas as pd
import numpy as np
import websocket
from datetime import datetime, UTC

# ========= CONFIG =========
API_KEY = os.getenv("db75d70b-f577-40e5-b06c-60b9c87584a7")
SECRET_KEY = os.getenv("DD0B0C2024162F50F4267C1D59C4AC81")
PASSPHRASE = os.getenv("WXcv8089@")

BASE_URL = "https://www.okx.com"

SYMBOLS = ["BTC-USDT-SWAP","ETH-USDT-SWAP","SOL-USDT-SWAP"]

RIESGO = 0.01
MAX_EXPOSURE = 0.3   # 30% del capital máximo en mercado
TP_GLOBAL = 0.015
SL_GLOBAL = -0.025

TIMEFRAME = "5m"
MARGIN_MODE = "isolated"

price_data = {}
ws_thread = None

# ========= LOG =========
def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

# ========= WS =========
def on_message(ws, message):
    try:
        data = json.loads(message)
        if "data" in data:
            for d in data["data"]:
                if "last" in d:
                    price_data[d["instId"]] = float(d["last"])
    except:
        pass

def on_open(ws):
    log("✅ WS conectado")
    args = [{"channel":"tickers","instId":s} for s in SYMBOLS]
    ws.send(json.dumps({"op":"subscribe","args":args}))

def on_close(ws, code, msg):
    log(f"⚠️ WS cerrado {code}")

def start_ws():
    global ws_thread

    if ws_thread and ws_thread.is_alive():
        return

    def run():
        while True:
            try:
                ws = websocket.WebSocketApp(
                    "wss://ws.okx.com:8443/ws/v5/public",
                    on_message=on_message,
                    on_open=on_open,
                    on_close=on_close
                )
                ws.run_forever(ping_interval=20)
            except Exception as e:
                log(f"WS error {e}")

            time.sleep(5)

    ws_thread = threading.Thread(target=run)
    ws_thread.daemon = True
    ws_thread.start()

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

# ========= IA INSTITUCIONAL =========
def ai_signal(df):
    try:
        if df is None or df.empty:
            return None

        close = df["close"]

        ema50 = close.ewm(span=50).mean().iloc[-1]
        ema200 = close.ewm(span=200).mean().iloc[-1]

        trend = "bull" if ema50 > ema200 else "bear"

        momentum = close.pct_change().iloc[-5:].mean()

        structure = close.iloc[-1] > close.iloc[-3]

        # filtro institucional
        if trend == "bull" and momentum > 0 and structure:
            return "buy"

        if trend == "bear" and momentum < 0 and not structure:
            return "sell"

        return None

    except:
        return None

# ========= RIESGO =========
def get_balance():
    try:
        r = requests.get(BASE_URL+"/api/v5/account/balance",
                         headers=headers("GET","/api/v5/account/balance"), timeout=5)
        for d in r.json()["data"][0]["details"]:
            if d["ccy"] == "USDT":
                return float(d["eq"])
    except:
        return 50

def get_size(balance, price):
    if not price:
        return 0
    return round((balance * RIESGO) / price, 3)

# ========= AUTH =========
def sign(ts, method, path, body=""):
    msg = f"{ts}{method}{path}{body}"
    return base64.b64encode(
        hmac.new(SECRET_KEY.encode(), msg.encode(), digestmod="sha256").digest()
    ).decode()

def headers(method, path, body=""):
    ts = datetime.utcnow().isoformat("T","milliseconds")+"Z"
    return {
        "OK-ACCESS-KEY": API_KEY,
        "OK-ACCESS-SIGN": sign(ts, method, path, body),
        "OK-ACCESS-TIMESTAMP": ts,
        "OK-ACCESS-PASSPHRASE": PASSPHRASE,
        "Content-Type": "application/json"
    }

# ========= TRADE =========
def place(symbol, side, price, balance):
    size = get_size(balance, price)
    if size <= 0:
        return

    body = json.dumps({
        "instId": symbol,
        "tdMode": MARGIN_MODE,
        "side": side,
        "ordType": "market",
        "sz": str(size)
    })

    try:
        r = requests.post(BASE_URL+"/api/v5/trade/order",
                          headers=headers("POST","/api/v5/trade/order",body),
                          data=body, timeout=5)
        log(f"🔥 {symbol} {side} ejecutado")
    except:
        log("❌ error orden")

# ========= BOT =========
def run():
    log("🏦 BOT INSTITUCIONAL ACTIVO")

    start_ws()

    while True:
        try:
            balance = get_balance()
            pnl = (balance - 50) / 50

            log(f"💰 {balance} USDT | PnL {round(pnl*100,2)}%")

            # KILL SWITCH
            if pnl <= SL_GLOBAL:
                log("🛑 KILL SWITCH ACTIVADO")
                time.sleep(300)
                continue

            if pnl >= TP_GLOBAL:
                log("🎯 TAKE PROFIT GLOBAL")
                time.sleep(120)
                continue

            for symbol in SYMBOLS:

                df = get_klines(symbol)
                if df is None:
                    continue

                signal = ai_signal(df)
                if not signal:
                    continue

                price = price_data.get(symbol)
                if not price:
                    price = df["close"].iloc[-1]

                log(f"📡 {symbol} → {signal}")

                place(symbol, signal, price, balance)

                break

            time.sleep(60)

        except:
            log(traceback.format_exc())
            time.sleep(30)

if __name__ == "__main__":
    run()