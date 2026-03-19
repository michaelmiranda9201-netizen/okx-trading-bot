import ccxt
import time
import pandas as pd

# =========================
# CONFIG
# =========================
API_KEY = "db75d70b-f577-40e5-b06c-60b9c87584a7"
API_SECRET = "DD0B0C2024162F50F4267C1D59C4AC81"
PASSPHRASE = "WXcv8089@"

MAX_TRADES = 2
COOLDOWN = 5

active_trades = {}
highest_pnl = {}

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
def get_df(symbol, tf):
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe=tf, limit=100)
    df = pd.DataFrame(ohlcv, columns=['time','open','high','low','close','volume'])

    df['ema20'] = df['close'].ewm(span=20).mean()
    df['ema50'] = df['close'].ewm(span=50).mean()
    df['momentum'] = df['close'].pct_change(3)

    return df

# =========================
# SCANNER TOP
# =========================
def scan_top():
    markets = exchange.load_markets()
    ranking = []

    for s in list(markets)[:30]:
        if ":USDT" not in s:
            continue

        try:
            df = get_df(s, '1h')
            score = abs(df['momentum'].iloc[-1])

            ranking.append((s, score))
        except:
            continue

    ranking.sort(key=lambda x: x[1], reverse=True)

    return [x[0] for x in ranking[:5]]

# =========================
# FILTRO FUERTE
# =========================
def strong_market(df):
    return abs(df['momentum'].iloc[-1]) > 0.002

# =========================
# SEÑALES
# =========================
def trend(df):
    last = df.iloc[-1]
    return "buy" if last['ema20'] > last['ema50'] else "sell"

def confirm(df, direction):
    last = df.iloc[-1]
    return (direction == "buy" and last['ema20'] > last['ema50']) or \
           (direction == "sell" and last['ema20'] < last['ema50'])

def sniper(df, direction):
    momentum = df['momentum'].iloc[-1]
    return (direction == "buy" and momentum > 0.004) or \
           (direction == "sell" and momentum < -0.004)

# =========================
# ENTRY
# =========================
def enter(symbol, balance, price, side):
    size = balance * 0.03 / price
    size = max(0.01, size)

    size = float(exchange.amount_to_precision(symbol, size))

    exchange.create_order(
        symbol=symbol,
        type="market",
        side=side,
        amount=size,
        params={"tdMode": "isolated"}
    )

    active_trades[symbol] = side
    highest_pnl[symbol] = 0

    print(f"🚀 ENTRY {symbol} {side}")

# =========================
# TRAILING PRO
# =========================
def manage(symbol, pos):
    entry = float(pos['entryPrice'])
    mark = float(pos['markPrice'])
    size = float(pos['contracts'])
    side = pos['side']

    pnl = (mark - entry) * size if side == "long" else (entry - mark) * size

    if pnl > highest_pnl[symbol]:
        highest_pnl[symbol] = pnl

    # 🔥 trailing dinámico
    if highest_pnl[symbol] > 0.3:
        if pnl < highest_pnl[symbol] - 0.2:
            exit_side = "sell" if side == "long" else "buy"

            exchange.create_order(
                symbol=symbol,
                type="market",
                side=exit_side,
                amount=size,
                params={"tdMode": "isolated"}
            )

            print(f"💰 TRAILING EXIT {symbol} {pnl:.2f}")

            del active_trades[symbol]
            del highest_pnl[symbol]

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
# LOOP
# =========================
def run():
    print("🔥 MODO BESTIA FINAL ACTIVADO")

    while True:
        try:
            balance = exchange.fetch_balance()['USDT']['free']

            # 🔥 gestionar trades activos
            for symbol in list(active_trades.keys()):
                pos = get_position(symbol)

                if pos:
                    manage(symbol, pos)
                else:
                    del active_trades[symbol]

            if len(active_trades) >= MAX_TRADES:
                time.sleep(2)
                continue

            # 🔥 buscar oportunidades
            for symbol in scan_top():

                if symbol in active_trades:
                    continue

                df1h = get_df(symbol, '1h')

                if not strong_market(df1h):
                    continue

                direction = trend(df1h)

                df5m = get_df(symbol, '5m')
                if not confirm(df5m, direction):
                    continue

                df1m = get_df(symbol, '1m')
                if not sniper(df1m, direction):
                    continue

                price = df1m['close'].iloc[-1]

                enter(symbol, balance, price, direction)
                break

            time.sleep(COOLDOWN)

        except Exception as e:
            print(f"❌ ERROR: {e}")
            time.sleep(5)

if __name__ == "__main__":
    run()