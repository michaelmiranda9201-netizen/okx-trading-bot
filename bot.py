import ccxt
import time
import pandas as pd

# =========================
# CONFIG
# =========================
API_KEY = "db75d70b-f577-40e5-b06c-60b9c87584a7"
API_SECRET = "DD0B0C2024162F50F4267C1D59C4AC81"
PASSPHRASE = "WXcv8089@"

SYMBOLS = [
    "BTC/USDT:USDT",
    "ETH/USDT:USDT",
    "SOL/USDT:USDT",
    "AVAX/USDT:USDT"
]

GRID_LEVELS = 3
MAX_DRAWDOWN = 0.06

start_balance = None

# =========================
# OKX
# =========================
exchange = ccxt.okx({
    'apiKey': API_KEY,
    'secret': API_SECRET,
    'password': PASSPHRASE,
    'enableRateLimit': True,
    'options': {
        'defaultType': 'swap',
        'defaultMarginMode': 'isolated'
    }
})

# =========================
# DATA
# =========================
def get_data(symbol):
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe='1m', limit=150)
    df = pd.DataFrame(ohlcv, columns=['time','open','high','low','close','volume'])

    df['ema20'] = df['close'].ewm(span=20).mean()
    df['ema50'] = df['close'].ewm(span=50).mean()
    df['atr'] = (df['high'] - df['low']).rolling(14).mean()

    return df

# =========================
# MERCADO
# =========================
def market_type(df):
    last = df.iloc[-1]
    trend = abs(last['ema20'] - last['ema50'])

    if trend > last['atr']:
        return "trend"
    else:
        return "range"

# =========================
# LEVERAGE DINÁMICO REAL
# =========================
def dynamic_leverage(atr, price):
    vol = atr / price

    if vol < 0.002:
        return 10
    elif vol < 0.005:
        return 7
    else:
        return 5

def set_leverage(symbol, lev):
    try:
        market = exchange.market(symbol)

        exchange.set_leverage(
            lev,
            market['id'],
            params={"mgnMode": "isolated"}
        )

        print(f"⚙️ Leverage x{lev} AISLADO")

    except Exception as e:
        print(f"❌ Error leverage: {e}")

# =========================
# LIMPIEZA
# =========================
def cancel_all(symbol):
    try:
        for o in exchange.fetch_open_orders(symbol):
            exchange.cancel_order(o['id'], symbol)

        try:
            exchange.private_post_trade_cancel_algos({
                "instId": exchange.market(symbol)['id']
            })
        except:
            pass

    except:
        pass

# =========================
# SELECCIÓN
# =========================
def choose_symbol():
    best = None
    best_score = 0

    for s in SYMBOLS:
        df = get_data(s)

        score = df['atr'].iloc[-1] / df['close'].iloc[-1]

        if score > best_score:
            best_score = score
            best = s

    return best

# =========================
# GRID
# =========================
def create_grid(df, balance):
    price = df['close'].iloc[-1]
    atr = df['atr'].iloc[-1]

    spacing = atr * 0.4
    size = max(0.01, balance * 0.02 / price)

    orders = []

    for i in range(1, GRID_LEVELS + 1):
        orders.append(("buy", price - spacing * i))
        orders.append(("sell", price + spacing * i))

    return orders, size

def place_grid(symbol, orders, size):
    for side, price in orders:
        try:
            exchange.create_order(
                symbol=symbol,
                type="limit",
                side=side,
                amount=size,
                price=price,
                params={"tdMode": "isolated"}
            )
            print(f"📌 GRID {side} @ {price:.2f}")
        except Exception as e:
            print(e)

# =========================
# SNIPER
# =========================
def sniper_signal(df):
    last = df.iloc[-1]

    high = df['high'].rolling(20).max().iloc[-1]
    low = df['low'].rolling(20).min().iloc[-1]

    price = last['close']

    if price > high:
        return "sell"

    if price < low:
        return "buy"

    return None

def sniper_entry(symbol, side, balance, price):
    size = max(0.01, balance * 0.03 / price)

    try:
        exchange.create_order(
            symbol=symbol,
            type="market",
            side=side,
            amount=size,
            params={"tdMode": "isolated"}
        )
        print(f"🎯 SNIPER {side.upper()}")
    except Exception as e:
        print(e)

# =========================
# RIESGO
# =========================
def risk_control(balance):
    global start_balance

    if start_balance is None:
        start_balance = balance

    dd = (start_balance - balance) / start_balance

    if dd >= MAX_DRAWDOWN:
        print("🛑 STOP GLOBAL")
        return False

    return True

# =========================
# LOOP
# =========================
def run():
    print("🔥 BOT HÍBRIDO PRO FINAL")

    while True:
        try:
            balance = exchange.fetch_balance()['USDT']['free']

            if not risk_control(balance):
                break

            symbol = choose_symbol()
            df = get_data(symbol)

            price = df['close'].iloc[-1]
            atr = df['atr'].iloc[-1]

            lev = dynamic_leverage(atr, price)

            cancel_all(symbol)
            set_leverage(symbol, lev)

            mkt = market_type(df)

            print(f"\n🎯 {symbol} | {mkt} | Lev x{lev}")

            # 🔥 SNIPER PRIORIDAD
            signal = sniper_signal(df)

            if signal:
                sniper_entry(symbol, signal, balance, price)
                time.sleep(20)
                continue

            # 🔥 GRID
            if mkt == "range":
                grid, size = create_grid(df, balance)
                place_grid(symbol, grid, size)

            time.sleep(20)

        except Exception as e:
            print(f"❌ ERROR: {e}")
            time.sleep(10)

if __name__ == "__main__":
    run()