import ccxt
import time
import pandas as pd

# =========================
# CONFIG
# =========================
API_KEY = "db75d70b-f577-40e5-b06c-60b9c87584a7"
API_SECRET = "DD0B0C2024162F50F4267C1D59C4AC81"
PASSPHRASE = "WXcv8089@"

MAX_DRAWDOWN = 0.1
COOLDOWN = 20

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
# DATA MULTI TF
# =========================
def get_df(symbol, tf):
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe=tf, limit=100)
    df = pd.DataFrame(ohlcv, columns=['time','open','high','low','close','volume'])

    df['ema20'] = df['close'].ewm(span=20).mean()
    df['ema50'] = df['close'].ewm(span=50).mean()
    df['atr'] = (df['high'] - df['low']).rolling(14).mean()

    return df

# =========================
# SCANNER
# =========================
def get_symbols():
    markets = exchange.load_markets()
    whitelist = ["BTC","ETH","SOL","DOGE","XRP","AVAX","LINK"]

    return [s for s in markets if ":USDT" in s and any(x in s for x in whitelist)]

def choose_symbol():
    best = None
    best_score = 0

    for s in get_symbols():
        try:
            df = get_df(s, '1h')
            score = df['atr'].iloc[-1] / df['close'].iloc[-1]

            if score > best_score:
                best_score = score
                best = s
        except:
            continue

    print(f"🎯 Mejor activo: {best}")
    return best

# =========================
# DIRECCIÓN (1H)
# =========================
def trend_1h(df):
    last = df.iloc[-1]

    if last['ema20'] > last['ema50']:
        return "buy"
    elif last['ema20'] < last['ema50']:
        return "sell"
    return None

# =========================
# CONFIRMACIÓN (5M)
# =========================
def confirm_5m(df, direction):
    last = df.iloc[-1]

    if direction == "buy" and last['ema20'] > last['ema50']:
        return True

    if direction == "sell" and last['ema20'] < last['ema50']:
        return True

    return False

# =========================
# SNIPER ENTRY (1M)
# =========================
def sniper_entry(df, direction):
    last = df.iloc[-1]

    high = df['high'].rolling(20).max().iloc[-1]
    low = df['low'].rolling(20).min().iloc[-1]
    price = last['close']

    if direction == "buy" and price < low:
        return True

    if direction == "sell" and price > high:
        return True

    return False

# =========================
# LEVERAGE
# =========================
def set_leverage(symbol):
    exchange.set_leverage(
        3,
        exchange.market(symbol)['id'],
        params={"mgnMode": "isolated"}
    )

# =========================
# SIZE
# =========================
def size_calc(symbol, balance, price):
    size = balance * 0.05 / price

    if size < 0.01:
        size = 0.01

    return float(exchange.amount_to_precision(symbol, size))

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
# GESTIÓN
# =========================
def manage(symbol, pos):
    entry = float(pos['entryPrice'])
    mark = float(pos['markPrice'])
    size = float(pos['contracts'])
    side = pos['side']

    pnl = (mark - entry) * size if side == "long" else (entry - mark) * size
    exit_side = "sell" if side == "long" else "buy"

    if pnl > 0:
        exchange.create_order(
            symbol=symbol,
            type="market",
            side=exit_side,
            amount=size,
            params={"tdMode": "isolated"}
        )
        print(f"💰 PROFIT {pnl:.2f}")

# =========================
# LOOP
# =========================
def run():
    print("🔥 MULTI TIMEFRAME SNIPER ACTIVADO")

    while True:
        try:
            balance = exchange.fetch_balance()['USDT']['free']

            symbol = choose_symbol()

            df1h = get_df(symbol, '1h')
            direction = trend_1h(df1h)

            if direction is None:
                time.sleep(20)
                continue

            df5m = get_df(symbol, '5m')

            if not confirm_5m(df5m, direction):
                time.sleep(20)
                continue

            df1m = get_df(symbol, '1m')

            if not sniper_entry(df1m, direction):
                time.sleep(10)
                continue

            set_leverage(symbol)

            pos = get_position(symbol)

            if pos:
                manage(symbol, pos)
            else:
                price = df1m['close'].iloc[-1]
                size = size_calc(symbol, balance, price)

                exchange.create_order(
                    symbol=symbol,
                    type="market",
                    side=direction,
                    amount=size,
                    params={"tdMode": "isolated"}
                )

                print(f"🚀 SNIPER ENTRY {symbol} {direction}")

            time.sleep(COOLDOWN)

        except Exception as e:
            print(f"❌ ERROR: {e}")
            time.sleep(5)

if __name__ == "__main__":
    run()