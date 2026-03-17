import time
import requests
import pandas as pd
import hmac, base64, json
from datetime import datetime, UTC

# ========= CONFIG =========
API_KEY = "db75d70b-f577-40e5-b06c-60b9c87584a7"
SECRET_KEY = "DD0B0C2024162F50F4267C1D59C4AC81"
PASSPHRASE = "WXcv8089@"

BASE_URL = "https://www.okx.com"

RIESGO = 0.05
TIMEFRAME = "5m"
MARGIN_MODE = "isolated"

# ========= LOG =========
def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

# ========= AUTH =========
def sign(ts, method, path, body=""):
    msg = f"{ts}{method}{path}{body}"
    return base64.b64encode(
        hmac.new(SECRET_KEY.encode(), msg.encode(), digestmod="sha256").digest()
    ).decode()

def headers(method, path, body=""):
    ts = datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00","Z")

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
    return df.sort_values("vol", ascending=False).head(3)["instId"].tolist()

def get_klines(symbol):
    r = requests.get(
        f"{BASE_URL}/api/v5/market/candles?instId={symbol}&bar={TIMEFRAME}&limit=100"
    ).json()

    df = pd.DataFrame(r["data"])
    df = df.iloc[:, :6]
    df.columns = ["time","open","high","low","close","volume"]

    return df.astype(float)[::-1]

# ========= BALANCE =========
def get_balance():
    try:
        r = requests.get(
            BASE_URL+"/api/v5/account/balance",
            headers=headers("GET","/api/v5/account/balance")
        ).json()

        log(f"📊 Balance raw: {r}")

        for d in r["data"][0]["details"]:
            if d["ccy"] == "USDT":
                return float(d["availEq"])
    except Exception as e:
        log(f"❌ error balance: {e}")

    return None

# ========= LOT SIZE FIX =========
def get_size(balance, price, symbol):

    size = (balance * RIESGO) / price

    # lot sizes por símbolo (OKX)
    lot_sizes = {
        "BTC-USDT-SWAP": 0.001,
        "ETH-USDT-SWAP": 0.01,
        "SOL-USDT-SWAP": 0.1
    }

    lot = lot_sizes.get(symbol, 0.001)

    # ajustar al múltiplo correcto
    size = max(size, lot)
    size = (size // lot) * lot

    return round(size, 6)

# ========= ORDEN =========
def place(symbol, side, price, balance):

    size = get_size(balance, price, symbol)

    if size <= 0:
        log("❌ tamaño inválido")
        return

    body = json.dumps({
        "instId": symbol,
        "tdMode": MARGIN_MODE,
        "side": side,
        "ordType": "market",   # 🔥 ejecución inmediata
        "sz": str(size)
    })

    try:
        r = requests.post(
            BASE_URL+"/api/v5/trade/order",
            headers=headers("POST","/api/v5/trade/order",body),
            data=body
        ).json()

        log(f"📊 OKX RESPUESTA: {r}")

    except Exception as e:
        log(f"❌ error orden: {e}")

# ========= BOT =========
def run():
    log("🚀 BOT OKX OPERATIVO (FIX LOT SIZE)")

    while True:
        try:
            balance = get_balance()

            if balance is None:
                log("❌ no balance")
                time.sleep(10)
                continue

            log(f"💰 Balance REAL: {balance}")

            if balance < 2:
                log("⚠️ saldo muy bajo")
                time.sleep(60)
                continue

            pares = get_pairs()

            for symbol in pares:

                df = get_klines(symbol)
                price = df["close"].iloc[-1]

                # 🔥 FORZAMOS BUY PARA TEST
                side = "buy"

                log(f"🔥 Ejecutando {symbol}")

                place(symbol, side, price, balance)

                break

            time.sleep(60)

        except Exception as e:
            log(f"❌ ERROR: {e}")
            time.sleep(10)

# ========= START =========
if __name__ == "__main__":
    run()