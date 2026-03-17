import ccxt
import time
import pandas as pd
import numpy as np

# =========================
# 🔐 CONFIG
# =========================
API_KEY = "db75d70b-f577-40e5-b06c-60b9c87584a7"
API_SECRET = "DD0B0C2024162F50F4267C1D59C4AC81"
PASSPHRASE = "WXcv8089@"

SYMBOLS = ["BTC/USDT:USDT", "ETH/USDT:USDT"]

TIMEFRAME = '1m'
RISK = 0.05

# =========================
# 🔌 OKX
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
# 📊 DATA + FILTROS PRO
# =========================
def get_data(symbol):
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=150)
    df = pd.DataFrame(ohlcv, columns=['time','open','high','low','close','volume'])

    df['ema20'] = df['close'].ewm(span=20).mean()
    df['ema50'] = df['close'].ewm(span=50).mean()
    df['atr'] = (df['high'] - df['low']).rolling(14).mean()

    # 🔥 FUERZA DE TENDENCIA
    df['momentum'] = df['close'].pct_change(5)

    return df

# =========================
# 🧠 FILTRO INTELIGENTE
# =========================
def smart_signal(df):
    last = df.iloc[-1]

    trend = "buy" if last['ema20'] > last['ema50'] else "sell"

    # 🔥 FILTRO ANTI-LATERAL
    if abs(last['momentum']) < 0.001:
        return None

    return trend

# =========================
# 🧠 MEJOR PAR
# =========================
def choose_symbol():
    best = None
    best_score = 0

    for s in SYMBOLS:
        df = get_data(s)
        atr = df['atr'].iloc[-1]
        price = df['close'].iloc[-1]
        momentum = abs(df['momentum'].iloc[-1])

        score = (atr / price) + momentum

        if score > best_score:
            best_score = score
            best = s

    return best

# =========================
# ⚙️ LEVERAGE DINÁMICO
# =========================
def dynamic_leverage(atr, price):
    vol = atr / price

    if vol < 0.002:
        return 10
    elif vol < 0.005:
        return 7
    else:
        return 5

# =========================
# 🧹 LIMPIEZA TOTAL
# =========================
def cleanup(symbol):
    try:
        orders = exchange.fetch_open_orders(symbol)
        for o in orders:
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
# ⚙️ LEVERAGE
# =========================
def set_leverage(symbol, lev):
    cleanup(symbol)

    exchange.set_leverage(
        lev,
        exchange.market(symbol)['id'],
        params={"mgnMode": "isolated"}
    )

# =========================
# 💰 SIZE
# =========================
def size_calc(symbol, balance, price, lev):
    value = balance * RISK * lev
    size = value / price

    if size < 0.01:
        size = 0.01

    return float(exchange.amount_to_precision(symbol, size))

# =========================
# 📊 POSICIÓN
# =========================
def get_position(symbol):
    try:
        pos = exchange.fetch_positions([symbol])
        for p in pos:
            if float(p['contracts']) > 0:
                return p
    except:
        pass
    return None

# =========================
# 🚀 ENTRADA
# =========================
def enter(symbol, side, size):
    exchange.create_order(
        symbol=symbol,
        type="market",
        side=side,
        amount=size,
        params={"tdMode": "isolated"}
    )
    print(f"🚀 ENTRY {side} {symbol}")

# =========================
# 🎯 GESTIÓN ULTRA
# =========================
def manage(symbol, pos, atr):
    entry = float(pos['entryPrice'])
    size = float(pos['contracts'])
    side = pos['side']
    mark = float(pos['markPrice'])

    profit = (mark - entry) if side == "long" else (entry - mark)

    # 🔥 BREAK EVEN
    if profit > atr * 0.3:
        sl = entry
    else:
        sl = entry - atr if side == "long" else entry + atr

    # 🔥 TRAILING PROFIT
    tp = entry + atr if side == "long" else entry - atr

    exit_side = "sell" if side == "long" else "buy"

    print(f"📊 Gestión | Profit: {profit:.2f}")

    exchange.create_order(
        symbol=symbol,
        type="trigger",
        side=exit_side,
        amount=size,
        price=tp,
        params={"triggerPx": tp, "tdMode": "isolated"}
    )

    exchange.create_order(
        symbol=symbol,
        type="trigger",
        side=exit_side,
        amount=size,
        price=sl,
        params={"triggerPx": sl, "tdMode": "isolated"}
    )

# =========================
# 🔁 LOOP
# =========================
def run():
    print("💣 ULTRA DIOS RUNNING")

    while True:
        try:
            balance = exchange.fetch_balance()['USDT']['free']

            symbol = choose_symbol()
            df = get_data(symbol)

            signal = smart_signal(df)

            if signal is None:
                print("⏸ Mercado lateral - no trade")
                time.sleep(20)
                continue

            price = df['close'].iloc[-1]
            atr = df['atr'].iloc[-1]

            lev = dynamic_leverage(atr, price)

            pos = get_position(symbol)

            if not pos:
                set_leverage(symbol, lev)
                size = size_calc(symbol, balance, price, lev)
                enter(symbol, signal, size)
            else:
                manage(symbol, pos, atr)

            time.sleep(25)

        except Exception as e:
            print(f"❌ ERROR: {e}")
            time.sleep(15)

if __name__ == "__main__":
    run()