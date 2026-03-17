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

TARGET_PROFIT = 1.0  # 🔥 1 USDT
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
# 📊 DATA
# =========================
def get_data(symbol):
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe='1m', limit=200)
    df = pd.DataFrame(ohlcv, columns=['time','open','high','low','close','volume'])

    df['ema20'] = df['close'].ewm(span=20).mean()
    df['ema50'] = df['close'].ewm(span=50).mean()
    df['atr'] = (df['high'] - df['low']).rolling(14).mean()

    df['momentum'] = df['close'].pct_change(3)
    df['vol_mean'] = df['volume'].rolling(20).mean()

    return df

# =========================
# 🧠 IA PREDICTIVA
# =========================
def ai_signal(df):
    last = df.iloc[-1]

    # volumen anormal (acumulación)
    vol_spike = last['volume'] > last['vol_mean'] * 1.8

    # movimiento anticipado
    momentum = last['momentum']

    # tendencia base
    trend = "buy" if last['ema20'] > last['ema50'] else "sell"

    if vol_spike and abs(momentum) > 0.001:
        return trend

    return None

# =========================
# 🐋 DETECTOR BALLENAS
# =========================
def whale_filter(df):
    last = df.iloc[-1]

    candle_range = last['high'] - last['low']
    atr = last['atr']

    # si vela muy grande → manipulación
    if candle_range > atr * 2.5:
        print("🐋 Ballena detectada - evitar entrada")
        return False

    return True

# =========================
# ⚙️ LEVERAGE
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
    cleanup(symbol)
    exchange.set_leverage(
        lev,
        exchange.market(symbol)['id'],
        params={"mgnMode": "isolated"}
    )

# =========================
# 🧹 CLEANUP
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
# 🚀 ENTRY
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
# 💰 MICRO PROFIT 1 USDT
# =========================
def manage(symbol, pos):
    entry = float(pos['entryPrice'])
    size = float(pos['contracts'])
    side = pos['side']
    mark = float(pos['markPrice'])

    pnl = (mark - entry) * size if side == "long" else (entry - mark) * size

    print(f"💰 PnL actual: {pnl:.2f} USDT")

    # 🔥 CIERRE EN 1 USDT
    if pnl >= TARGET_PROFIT:
        exit_side = "sell" if side == "long" else "buy"

        exchange.create_order(
            symbol=symbol,
            type="market",
            side=exit_side,
            amount=size,
            params={"tdMode": "isolated"}
        )

        print("💵 GANANCIA ASEGURADA +1 USDT")

# =========================
# 🧠 MEJOR PAR
# =========================
def choose_symbol():
    best = None
    best_score = 0

    for s in SYMBOLS:
        df = get_data(s)
        score = abs(df['momentum'].iloc[-1]) + (df['atr'].iloc[-1] / df['close'].iloc[-1])

        if score > best_score:
            best_score = score
            best = s

    return best

# =========================
# 🔁 LOOP
# =========================
def run():
    print("🧠 IA + 🐋 BOT ACTIVADO")

    while True:
        try:
            balance = exchange.fetch_balance()['USDT']['free']

            symbol = choose_symbol()
            df = get_data(symbol)

            if not whale_filter(df):
                time.sleep(20)
                continue

            signal = ai_signal(df)

            if signal is None:
                print("⏸ Sin señal IA")
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
                manage(symbol, pos)

            time.sleep(20)

        except Exception as e:
            print(f"❌ ERROR: {e}")
            time.sleep(15)

if __name__ == "__main__":
    run()