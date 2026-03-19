import ccxt
import time
import pandas as pd

# =========================
# CONFIG
# =========================
API_KEY = "db75d70b-f577-40e5-b06c-60b9c87584a7"
API_SECRET = DD0B0C2024162F50F4267C1D59C4AC81"
PASSPHRASE = "WXcv8089@"

COOLDOWN = 5
TRAILING_TRIGGER = 0.3  # USDT
TRAILING_GAP = 0.2

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
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe='1m', limit=50)
    df = pd.DataFrame(ohlcv, columns=['time','open','high','low','close','volume'])

    df['momentum'] = df['close'].pct_change(2)
    df['vol_avg'] = df['volume'].rolling(10).mean()

    return df

# =========================
# DETECTOR ULTRA PUMP
# =========================
def is_ultra_pump(df):
    momentum = df['momentum'].iloc[-1]
    volume = df['volume'].iloc[-1]
    vol_avg = df['vol_avg'].iloc[-1]

    # 🔥 condiciones fuertes
    if momentum > 0.015 and volume > vol_avg * 2:
        return True

    return False

# =========================
# ANTI FAKE
# =========================
def not_late(df):
    last = df.iloc[-1]
    prev = df.iloc[-2]

    # 🔥 evita entrar en pico
    if last['close'] > prev['close'] * 1.02:
        return False

    return True

# =========================
# SCANNER
# =========================
def find_token():
    markets = exchange.load_markets()

    best = None
    best_score = 0

    for s in markets:
        if ":USDT" not in s:
            continue

        try:
            df = get_data(s)

            if not is_ultra_pump(df):
                continue

            if not not_late(df):
                continue

            score = df['momentum'].iloc[-1]

            if score > best_score:
                best_score = score
                best = s

        except:
            continue

    print(f"🎯 ULTRA TOKEN: {best}")
    return best

# =========================
# POSICIÓN
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
# ENTRY
# =========================
def enter(symbol, balance, price):
    size = balance * 0.04 / price

    if size < 0.01:
        size = 0.01

    size = float(exchange.amount_to_precision(symbol, size))

    exchange.create_order(
        symbol=symbol,
        type="market",
        side="buy",
        amount=size,
        params={"tdMode": "isolated"}
    )

    print(f"🚀 ULTRA ENTRY {symbol}")

# =========================
# TRAILING STOP
# =========================
highest_pnl = 0

def manage(symbol, pos):
    global highest_pnl

    entry = float(pos['entryPrice'])
    mark = float(pos['markPrice'])
    size = float(pos['contracts'])

    pnl = (mark - entry) * size

    if pnl > highest_pnl:
        highest_pnl = pnl

    # 🔥 activar trailing
    if highest_pnl > TRAILING_TRIGGER:

        if pnl < highest_pnl - TRAILING_GAP:
            exchange.create_order(
                symbol=symbol,
                type="market",
                side="sell",
                amount=size,
                params={"tdMode": "isolated"}
            )

            print(f"💰 TRAILING EXIT {pnl:.2f}")
            highest_pnl = 0

# =========================
# LOOP
# =========================
def run():
    print("🔥 ULTRA SNIPER ACTIVADO")

    current = None

    while True:
        try:
            balance = exchange.fetch_balance()['USDT']['free']

            if current:
                pos = get_position(current)

                if pos:
                    manage(current, pos)
                    time.sleep(2)
                    continue
                else:
                    current = None

            symbol = find_token()

            if not symbol:
                time.sleep(5)
                continue

            df = get_data(symbol)
            price = df['close'].iloc[-1]

            enter(symbol, balance, price)
            current = symbol

            time.sleep(COOLDOWN)

        except Exception as e:
            print(f"❌ ERROR: {e}")
            time.sleep(5)

if __name__ == "__main__":
    run()