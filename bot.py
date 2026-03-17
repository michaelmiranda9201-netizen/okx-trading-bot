import ccxt
import time
import pandas as pd

# =========================
# 🔐 CONFIG
# =========================
API_KEY = "db75d70b-f577-40e5-b06c-60b9c87584a7"
API_SECRET = "DD0B0C2024162F50F4267C1D59C4AC81"
PASSPHRASE = "WXcv8089@"

SYMBOLS = ["BTC/USDT:USDT", "ETH/USDT:USDT"]

RISK = 0.05
MAX_DRAWDOWN = 0.05  # 5% pérdida máxima diaria
COOLDOWN = 60  # segundos entre trades

start_balance = None
last_trade_time = 0

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
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe='1m', limit=150)
    df = pd.DataFrame(ohlcv, columns=['time','open','high','low','close','volume'])

    df['ema20'] = df['close'].ewm(span=20).mean()
    df['ema50'] = df['close'].ewm(span=50).mean()
    df['atr'] = (df['high'] - df['low']).rolling(14).mean()
    df['adx'] = abs(df['ema20'] - df['ema50'])

    return df

# =========================
# 🧠 FILTRO MERCADO
# =========================
def market_ok(df):
    last = df.iloc[-1]

    # evitar lateral
    if last['adx'] < last['atr'] * 0.3:
        return False

    return True

# =========================
# 🧠 SEÑAL
# =========================
def get_signal(df):
    last = df.iloc[-1]
    return "buy" if last['ema20'] > last['ema50'] else "sell"

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
# 🎯 GESTIÓN PROFESIONAL
# =========================
def manage(symbol, pos, atr):
    entry = float(pos['entryPrice'])
    size = float(pos['contracts'])
    side = pos['side']
    mark = float(pos['markPrice'])

    pnl = (mark - entry) * size if side == "long" else (entry - mark) * size

    # 🔥 PROFIT DINÁMICO
    target = atr * size * 1.2

    # 🔥 TRAILING
    if pnl > target * 0.5:
        sl = entry  # break-even
    else:
        sl = entry - atr if side == "long" else entry + atr

    # 🔥 TP dinámico
    tp = entry + atr * 1.5 if side == "long" else entry - atr * 1.5

    exit_side = "sell" if side == "long" else "buy"

    print(f"💰 PnL: {pnl:.2f} | Target: {target:.2f}")

    if pnl >= target:
        exchange.create_order(
            symbol=symbol,
            type="market",
            side=exit_side,
            amount=size,
            params={"tdMode": "isolated"}
        )
        print("💵 PROFIT CERRADO")

# =========================
# 🛑 CONTROL RIESGO
# =========================
def risk_control(balance):
    global start_balance

    if start_balance is None:
        start_balance = balance

    drawdown = (start_balance - balance) / start_balance

    if drawdown >= MAX_DRAWDOWN:
        print("🛑 STOP GLOBAL ACTIVADO")
        return False

    return True

# =========================
# 🧠 MEJOR PAR
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
# 🔁 LOOP
# =========================
def run():
    global last_trade_time

    print("🔥 BOT RENTABLE ACTIVADO")

    while True:
        try:
            balance = exchange.fetch_balance()['USDT']['free']

            if not risk_control(balance):
                break

            symbol = choose_symbol()
            df = get_data(symbol)

            if not market_ok(df):
                print("⏸ Mercado lateral")
                time.sleep(20)
                continue

            signal = get_signal(df)

            price = df['close'].iloc[-1]
            atr = df['atr'].iloc[-1]
            lev = dynamic_leverage(atr, price)

            pos = get_position(symbol)

            # evitar sobreoperar
            if time.time() - last_trade_time < COOLDOWN:
                time.sleep(10)
                continue

            if not pos:
                set_leverage(symbol, lev)
                size = size_calc(symbol, balance, price, lev)
                enter(symbol, signal, size)
                last_trade_time = time.time()
            else:
                manage(symbol, pos, atr)

            time.sleep(20)

        except Exception as e:
            print(f"❌ ERROR: {e}")
            time.sleep(15)

if __name__ == "__main__":
    run()