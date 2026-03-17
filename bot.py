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

GRID_CAPITAL = 15
MAX_POSITIONS = 1

# ========= AUTH =========
def headers(method, path, body=""):
    ts = str(time.time())
    msg = ts + method + path + body
    sign = base64.b64encode(
        hmac.new(API_SECRET.encode(), msg.encode(), hashlib.sha256).digest()
    ).decode()

    return {
        "OK-ACCESS-KEY": API_KEY,
        "OK-ACCESS-SIGN": sign,
        "OK-ACCESS-TIMESTAMP": ts,
        "OK-ACCESS-PASSPHRASE": PASSPHRASE,
        "Content-Type": "application/json"
    }

# ========= API =========
def candles(symbol):
    url = f"{BASE_URL}/api/v5/market/candles?instId={symbol}&bar=5m&limit=100"
    return requests.get(url).json()

def price(symbol):
    url = f"{BASE_URL}/api/v5/market/ticker?instId={symbol}"
    return float(requests.get(url).json()['data'][0]['last'])

def set_leverage(symbol, lev):
    path = "/api/v5/account/set-leverage"
    body = f'{{"instId":"{symbol}","lever":"{lev}","mgnMode":"isolated"}}'
    requests.post(BASE_URL + path, headers=headers("POST", path, body), data=body)

# ========= DATA =========
def df_format(data):
    df = pd.DataFrame(data['data'])
    df = df.iloc[::-1]
    df.columns = ["t","o","h","l","c","v","v2","v3","x"]
    df["c"] = df["c"].astype(float)
    df["h"] = df["h"].astype(float)
    df["l"] = df["l"].astype(float)
    return df

def indicators(df):
    df["ema50"] = df["c"].ewm(span=50).mean()
    df["ema200"] = df["c"].ewm(span=200).mean()
    df["atr"] = (df["h"] - df["l"]).rolling(14).mean()
    return df

# ========= FILTROS =========
def is_lateral(df):
    last = df.iloc[-1]
    trend = abs(last["ema50"] - last["ema200"])
    atr = last["atr"]

    # filtro anti tendencia
    if trend < atr * 2:
        return True
    return False

def detect_range(df):
    high = df["h"].rolling(50).max().iloc[-1]
    low = df["l"].rolling(50).min().iloc[-1]
    return low, high

# ========= GRID =========
def build_grid(price, low, high, atr):
    rng = high - low
    levels = int(rng / (atr * 0.5))
    levels = max(3, min(6, levels))
    step = rng / levels
    return step, levels

def leverage(atr, price):
    return 3 if atr/price > 0.01 else 5

# ========= ORDERS =========
def order(symbol, side, px, sz):
    path = "/api/v5/trade/order"
    body = f'''
    {{
        "instId":"{symbol}",
        "tdMode":"isolated",
        "side":"{side}",
        "ordType":"limit",
        "px":"{px}",
        "sz":"{sz}"
    }}
    '''
    requests.post(BASE_URL + path, headers=headers("POST", path, body), data=body)

def stop_loss(symbol, sl):
    path = "/api/v5/trade/order"
    body = f'''
    {{
        "instId":"{symbol}",
        "tdMode":"isolated",
        "side":"sell",
        "ordType":"market",
        "slTriggerPx":"{sl}",
        "slOrdPx":"-1"
    }}
    '''
    requests.post(BASE_URL + path, headers=headers("POST", path, body), data=body)

# ========= GRID EXEC =========
def place_grid(symbol, price, step, levels):
    qty = GRID_CAPITAL / levels / price

    for i in range(1, levels+1):
        buy = price - step * i
        sell = price + step * i

        order(symbol, "buy", round(buy, 2), round(qty, 3))
        order(symbol, "sell", round(sell, 2), round(qty, 3))

# ========= BOT =========
def run():
    while True:
        best = None
        best_atr = 0

        # 🔍 RADAR
        for s in SYMBOLS:
            try:
                data = candles(s)
                df = indicators(df_format(data))

                if not is_lateral(df):
                    continue

                atr = df["atr"].iloc[-1]

                if atr > best_atr:
                    best = s
                    best_atr = atr
            except:
                continue

        if best:
            print(f"\n🔥 TRADE: {best}")

            data = candles(best)
            df = indicators(df_format(data))

            price_now = df["c"].iloc[-1]
            atr = df["atr"].iloc[-1]

            low, high = detect_range(df)
            step, levels = build_grid(price_now, low, high, atr)

            lev = leverage(atr, price_now)
            set_leverage(best, lev)

            sl = low - atr * 1.2

            print(f"Precio: {price_now}")
            print(f"Rango: {low}-{high}")
            print(f"Grid: {levels}")
            print(f"Leverage: {lev}x")
            print(f"SL: {sl}")

            place_grid(best, price_now, step, levels)
            stop_loss(best, sl)

        time.sleep(300)

# ========= START =========
if __name__ == "__main__":
    run()