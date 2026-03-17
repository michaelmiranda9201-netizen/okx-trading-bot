import requests
import time
import hmac
import base64
import hashlib
import pandas as pd

# ========= CONFIG =========
API_KEY = "db75d70b-f577-40e5-b06c-60b9c87584a7"
API_SECRET = "DD0B0C2024162F50F4267C1D59C4AC81"
PASSPHRASE = "WXcv8089@"

BASE_URL = "https://www.okx.com"

SYMBOLS = ["BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP"]

CAPITAL = 50
GRID_CAPITAL = 20

# ========= AUTH =========
def get_headers(method, path, body=""):
    timestamp = str(time.time())
    message = timestamp + method + path + body

    signature = base64.b64encode(
        hmac.new(API_SECRET.encode(), message.encode(), hashlib.sha256).digest()
    ).decode()

    return {
        "OK-ACCESS-KEY": API_KEY,
        "OK-ACCESS-SIGN": signature,
        "OK-ACCESS-TIMESTAMP": timestamp,
        "OK-ACCESS-PASSPHRASE": PASSPHRASE,
        "Content-Type": "application/json"
    }

# ========= MARKET =========
def get_klines(instId):
    url = f"{BASE_URL}/api/v5/market/candles?instId={instId}&bar=5m&limit=100"
    return requests.get(url).json()

def get_price(instId):
    url = f"{BASE_URL}/api/v5/market/ticker?instId={instId}"
    return float(requests.get(url).json()['data'][0]['last'])

# ========= ACCOUNT =========
def set_leverage(instId, lev):
    path = "/api/v5/account/set-leverage"
    body = f'{{"instId":"{instId}","lever":"{lev}","mgnMode":"isolated"}}'
    headers = get_headers("POST", path, body)
    requests.post(BASE_URL + path, headers=headers, data=body)

# ========= STRATEGY =========
def prepare_df(data):
    df = pd.DataFrame(data['data'])
    df = df.iloc[::-1]

    df.columns = ["time","open","high","low","close","vol","volCcy","volCcyQuote","confirm"]

    df["close"] = df["close"].astype(float)
    df["high"] = df["high"].astype(float)
    df["low"] = df["low"].astype(float)

    return df

def indicators(df):
    df["ema50"] = df["close"].ewm(span=50).mean()
    df["ema200"] = df["close"].ewm(span=200).mean()
    df["atr"] = (df["high"] - df["low"]).rolling(14).mean()
    return df

def detect_range(df):
    high = df["high"].rolling(50).max().iloc[-1]
    low = df["low"].rolling(50).min().iloc[-1]
    return low, high

def build_grid(price, low, high, atr):
    range_size = high - low

    levels = int(range_size / (atr * 0.5))
    levels = max(3, min(levels, 6))

    step = range_size / levels

    return step, levels

def dynamic_leverage(atr, price):
    if atr / price > 0.01:
        return 3
    return 5

def dynamic_sl_tp(low, atr, step):
    sl = low - atr * 1.2
    tp = step * 0.7
    return sl, tp

# ========= EXECUTION =========
def place_order(instId, side, price, size):
    path = "/api/v5/trade/order"

    body = f'''
    {{
        "instId": "{instId}",
        "tdMode": "isolated",
        "side": "{side}",
        "ordType": "limit",
        "px": "{price}",
        "sz": "{size}"
    }}
    '''

    headers = get_headers("POST", path, body)
    requests.post(BASE_URL + path, headers=headers, data=body)

def place_grid(instId, price, step, levels):
    qty = GRID_CAPITAL / levels / price

    for i in range(1, levels + 1):
        buy = price - step * i
        sell = price + step * i

        place_order(instId, "buy", round(buy, 2), round(qty, 3))
        place_order(instId, "sell", round(sell, 2), round(qty, 3))

# ========= MAIN =========
def run():
    while True:
        best_symbol = None
        best_vol = 0

        # 🔍 Radar
        for sym in SYMBOLS:
            try:
                data = get_klines(sym)
                df = prepare_df(data)
                df = indicators(df)

                atr = df["atr"].iloc[-1]

                if atr > best_vol:
                    best_vol = atr
                    best_symbol = sym
            except:
                continue

        if best_symbol:
            print(f"\n🔥 OPERANDO: {best_symbol}")

            data = get_klines(best_symbol)
            df = prepare_df(data)
            df = indicators(df)

            price = df["close"].iloc[-1]
            atr = df["atr"].iloc[-1]

            low, high = detect_range(df)
            step, levels = build_grid(price, low, high, atr)

            lev = dynamic_leverage(atr, price)
            set_leverage(best_symbol, lev)

            sl, tp = dynamic_sl_tp(low, atr, step)

            print(f"Precio: {price}")
            print(f"Rango: {low} - {high}")
            print(f"Grid: {levels} niveles | Step: {step}")
            print(f"Leverage: {lev}x")
            print(f"SL: {sl} | TP: {tp}")

            place_grid(best_symbol, price, step, levels)

        time.sleep(300)

# ========= START =========
if __name__ == "__main__":
    run()