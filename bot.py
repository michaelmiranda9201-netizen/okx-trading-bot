import ccxt
import time
import pandas as pd

# =========================
# 🔐 CONFIG
# =========================
API_KEY = "db75d70b-f577-40e5-b06c-60b9c87584a7"
API_SECRET = "DD0B0C2024162F50F4267C1D59C4AC81"
PASSPHRASE = "WXcv8089@"

SYMBOLS = [
    "BTC/USDT:USDT",
    "ETH/USDT:USDT",
    "SOL/USDT:USDT",
    "AVAX/USDT:USDT",
    "LINK/USDT:USDT",
    "DOGE/USDT:USDT",
    "XRP/USDT:USDT"
]

RISK_BASE = 0.05
MAX_DRAWDOWN = 0.06
COOLDOWN = 30

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
    df['momentum'] = df['close'].pct_change(3)
    df['vol_avg'] = df['volume'].rolling(20).mean()

    return df

# =========================
# 🧠 DETECTAR MERCADO
# =========================
def detect_market(df):
    last = df.iloc[-1]

    strength = abs(last['ema20'] - last['ema50'])
    volatility = last['atr'] / last['close']

    if strength > last['atr'] * 0.8:
        return "trend"
    elif volatility < 0.002:
        return "dead"
    else:
        return "normal"

# =========================
# 🧠 SEÑAL
# =========================
def get_signal(df):
    last = df.iloc[-1]

    if abs(last['momentum']) < 0.001:
        return None

    if last['volume'] < last['vol_avg']:
        return None

    return "buy" if last['ema20'] > last['ema50'] else "sell"

# =========================
# 🧠 SELECCIÓN DE ACTIVO
# =========================
def choose_symbol():
    best = None
    best_score = 0

    for s in SYMBOLS:
        df = get_data(s)

        atr = df['atr'].iloc[-1]
        price = df['close'].iloc[-1]
        momentum = abs(df['momentum'].iloc[-1])
        volume = df['volume'].iloc[-1]
        vol_avg = df['vol_avg'].iloc[-1]

        # filtro mínimo
        if volume < vol_avg:
            continue

        score = (atr / price) * 2 + momentum + (volume / vol_avg)

        if "SOL" in s or "AVAX" in s:
            score *= 1.2

        if score > best_score:
            best_score = score
            best = s

    if best is None:
        print("⏸ Ningún activo óptimo")
        return None

    print(f"🎯 Activo seleccionado: {best}")
    return best

# =========================
# ⚙️ RISK + LEVERAGE
# =========================
def get_risk_and_lev(market_type, atr, price):
    vol = atr / price

    if market_type == "trend":
        return 0.08, 10
    elif market_type == "normal":
        return 0.06, 7
    else:
        return 0.03, 5

def set_leverage(symbol, lev):
    exchange.set_leverage(
        lev,
        exchange.market(symbol)['id'],
        params={"mgnMode": "isolated"}
    )

# =========================
# 💰 SIZE
# =========================
def size_calc(symbol, balance, price, risk, lev):
    value = balance * risk * lev
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
# 🎯 GESTIÓN
# =========================
def manage(symbol, pos, atr, market_type):
    entry = float(pos['entryPrice'])
    size = float(pos['contracts'])
    side = pos['side']
    mark = float(pos['markPrice'])

    pnl = (mark - entry) * size if side == "long" else (entry - mark) * size
    exit_side = "sell" if side == "long" else "buy"

    if market_type == "trend":
        target = atr * size * 2.5
    elif market_type == "normal":
        target = atr * size * 1.5
    else:
        target = atr * size * 0.8

    print(f"💰 PnL: {pnl:.2f} | Target: {target:.2f} | Mode: {market_type}")

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
# 🛑 RIESGO GLOBAL
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
# 🔁 LOOP
# =========================
def run():
    global last_trade_time

    print("🔥 BOT PRO ADAPTATIVO + MULTI-ACTIVOS")

    while True:
        try:
            balance = exchange.fetch_balance()['USDT']['free']

            if not risk_control(balance):
                break

            symbol = choose_symbol()

            if symbol is None:
                time.sleep(20)
                continue

            df = get_data(symbol)
            market_type = detect_market(df)
            signal = get_signal(df)

            if market_type == "dead" or signal is None:
                print("⏸ Mercado no óptimo")
                time.sleep(20)
                continue

            price = df['close'].iloc[-1]
            atr = df['atr'].iloc[-1]

            risk, lev = get_risk_and_lev(market_type, atr, price)

            pos = get_position(symbol)

            if time.time() - last_trade_time < COOLDOWN:
                time.sleep(10)
                continue

            if not pos:
                set_leverage(symbol, lev)
                size = size_calc(symbol, balance, price, risk, lev)
                enter(symbol, signal, size)
                last_trade_time = time.time()
            else:
                manage(symbol, pos, atr, market_type)

            time.sleep(15)

        except Exception as e:
            print(f"❌ ERROR: {e}")
            time.sleep(10)

# =========================
# ▶️ START
# =========================
if __name__ == "__main__":
    run()