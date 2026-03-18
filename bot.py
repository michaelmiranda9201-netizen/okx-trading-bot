import ccxt
import time
import pandas as pd

# =========================
# CONFIG
# =========================
API_KEY = "db75d70b-f577-40e5-b06c-60b9c87584a7"
API_SECRET = "DD0B0C2024162F50F4267C1D59C4AC81"
PASSPHRASE = "WXcv8089@"

MAX_DRAWDOWN = 0.06
GRID_LEVELS = 2  # 🔥 reducido para evitar error

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
# BALANCE SEGURO
# =========================
def get_safe_balance():
    balance = exchange.fetch_balance()['USDT']['free']
    return balance * 0.3  # 🔥 solo usar 30%

# =========================
# TIMEFRAME DINÁMICO
# =========================
def choose_timeframe(atr, price):
    vol = atr / price

    if vol < 0.002:
        return '1m'
    elif vol < 0.005:
        return '3m'
    else:
        return '5m'

# =========================
# DATA
# =========================
def get_data(symbol):
    base = exchange.fetch_ohlcv(symbol, timeframe='1m', limit=50)
    df_base = pd.DataFrame(base, columns=['time','open','high','low','close','volume'])

    atr = (df_base['high'] - df_base['low']).rolling(14).mean().iloc[-1]
    price = df_base['close'].iloc[-1]

    tf = choose_timeframe(atr, price)

    ohlcv = exchange.fetch_ohlcv(symbol, timeframe=tf, limit=100)
    df = pd.DataFrame(ohlcv, columns=['time','open','high','low','close','volume'])

    df['ema20'] = df['close'].ewm(span=20).mean()
    df['ema50'] = df['close'].ewm(span=50).mean()
    df['atr'] = (df['high'] - df['low']).rolling(14).mean()

    return df

# =========================
# LEVERAGE DINÁMICO
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
        exchange.set_leverage(
            lev,
            exchange.market(symbol)['id'],
            params={"mgnMode": "isolated"}
        )
    except:
        pass

# =========================
# SIZE SEGURO
# =========================
def calculate_size(symbol, balance, price, leverage):
    usable = balance * 0.5
    position_value = usable * leverage

    size = position_value / price

    if size < 0.01:
        size = 0.01

    return float(exchange.amount_to_precision(symbol, size))

# =========================
# SNIPER
# =========================
def sniper_signal(df):
    high = df['high'].rolling(20).max().iloc[-1]
    low = df['low'].rolling(20).min().iloc[-1]
    price = df['close'].iloc[-1]

    if price > high:
        return "sell"
    if price < low:
        return "buy"
    return None

# =========================
# GRID
# =========================
def create_grid(df, balance):
    price = df['close'].iloc[-1]
    atr = df['atr'].iloc[-1]

    spacing = atr * 0.4
    size = max(0.01, balance * 0.01 / price)

    orders = []

    for i in range(1, GRID_LEVELS + 1):
        orders.append(("buy", price - spacing * i))
        orders.append(("sell", price + spacing * i))

    return orders, size

# =========================
# LIMPIAR
# =========================
def cancel_orders(symbol):
    try:
        for o in exchange.fetch_open_orders(symbol):
            exchange.cancel_order(o['id'], symbol)
    except:
        pass

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
    print("🔥 BOT CORREGIDO ACTIVADO")

    SYMBOL = "BTC/USDT:USDT"  # 🔥 empezar simple

    while True:
        try:
            balance_total = exchange.fetch_balance()['USDT']['free']

            if balance_total < 5:
                print("⚠️ Balance bajo")
                time.sleep(30)
                continue

            if not risk_control(balance_total):
                break

            balance = get_safe_balance()

            df = get_data(SYMBOL)

            price = df['close'].iloc[-1]
            atr = df['atr'].iloc[-1]

            lev = dynamic_leverage(atr, price)

            cancel_orders(SYMBOL)
            set_leverage(SYMBOL, lev)

            print(f"\n🎯 {SYMBOL} | Lev x{lev}")

            # SNIPER
            signal = sniper_signal(df)

            if signal:
                size = calculate_size(SYMBOL, balance, price, lev)

                exchange.create_order(
                    symbol=SYMBOL,
                    type="market",
                    side=signal,
                    amount=size,
                    params={"tdMode": "isolated"}
                )

                print(f"🎯 SNIPER {signal}")
                time.sleep(20)
                continue

            # GRID
            grid, size = create_grid(df, balance)

            for side, p in grid:
                exchange.create_order(
                    symbol=SYMBOL,
                    type="limit",
                    side=side,
                    amount=size,
                    price=p,
                    params={"tdMode": "isolated"}
                )

            time.sleep(20)

        except Exception as e:
            print(f"❌ ERROR: {e}")
            time.sleep(10)

# =========================
# START
# =========================
if __name__ == "__main__":
    run()