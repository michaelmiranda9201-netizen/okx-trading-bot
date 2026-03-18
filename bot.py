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
TOP_SYMBOLS = 15

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
# OBTENER TODOS LOS PARES
# =========================
def get_all_symbols():
    markets = exchange.load_markets()
    symbols = []

    for m in markets:
        if "USDT" in m and ":USDT" in m:
            symbols.append(m)

    return symbols

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

    df['atr'] = (df['high'] - df['low']).rolling(14).mean()
    df['momentum'] = df['close'].pct_change(3)

    return df

# =========================
# SCANNER PRO
# =========================
def scan_market():
    symbols = get_all_symbols()

    ranking = []

    for s in symbols[:30]:  # limitar para velocidad
        try:
            df = get_data(s)

            atr = df['atr'].iloc[-1]
            price = df['close'].iloc[-1]
            momentum = abs(df['momentum'].iloc[-1])
            volume = df['volume'].iloc[-1]

            score = (atr / price) * 2 + momentum + (volume)

            ranking.append((s, score))

        except:
            continue

    ranking = sorted(ranking, key=lambda x: x[1], reverse=True)

    return [x[0] for x in ranking[:TOP_SYMBOLS]]

# =========================
# ELEGIR MEJOR
# =========================
def choose_symbol():
    top = scan_market()

    best = top[0]

    print(f"🎯 Mejor activo: {best}")

    return best

# =========================
# LEVERAGE
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
    exchange.set_leverage(
        lev,
        exchange.market(symbol)['id'],
        params={"mgnMode": "isolated"}
    )

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
    size = max(0.01, balance * 0.02 / price)

    orders = []

    for i in range(1, 3):
        orders.append(("buy", price - spacing * i))
        orders.append(("sell", price + spacing * i))

    return orders, size

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
    print("🔥 BOT SUPREMO ACTIVADO")

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
            set_leverage(symbol, lev)

            print(f"\n🎯 {symbol} | Lev x{lev}")

            # SNIPER
            signal = sniper_signal(df)

            if signal:
                size = max(0.01, balance * 0.03 / price)

                exchange.create_order(
                    symbol=symbol,
                    type="market",
                    side=signal,
                    amount=size,
                    params={"tdMode": "isolated"}
                )

                print(f"🎯 SNIPER {signal}")
                time.sleep(20)
                continue

            # GRID
            orders, size = create_grid(df, balance)

            for side, p in orders:
                exchange.create_order(
                    symbol=symbol,
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

if __name__ == "__main__":
    run()