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
COOLDOWN = 8

TOP_SYMBOLS = 10

# martingala
martingale_level = 1
MAX_MARTINGALE = 3

loss_streak = 0
MAX_LOSS_STREAK = 3
PAUSE_TIME = 120

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
# SCANNER GLOBAL
# =========================
def get_symbols():
    markets = exchange.load_markets()
    return [s for s in markets if ":USDT" in s]

def get_data(symbol, tf='1m'):
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe=tf, limit=100)
    df = pd.DataFrame(ohlcv, columns=['time','open','high','low','close','volume'])

    df['ema20'] = df['close'].ewm(span=20).mean()
    df['ema50'] = df['close'].ewm(span=50).mean()
    df['atr'] = (df['high'] - df['low']).rolling(14).mean()
    df['momentum'] = df['close'].pct_change(3)

    return df

def scan_market():
    symbols = get_symbols()
    ranking = []

    for s in symbols[:30]:
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

    ranking.sort(key=lambda x: x[1], reverse=True)

    return [x[0] for x in ranking[:TOP_SYMBOLS]]

def choose_symbol():
    top = scan_market()

    if not top:
        return None

    best = top[0]
    print(f"🎯 Mejor activo: {best}")
    return best

# =========================
# FILTRO MERCADO
# =========================
def market_ok(df):
    atr = df['atr'].iloc[-1]
    price = df['close'].iloc[-1]

    return (atr / price) > 0.0015

# =========================
# LEVERAGE
# =========================
def dynamic_leverage(atr, price):
    vol = atr / price

    if vol < 0.002:
        return 3
    elif vol < 0.005:
        return 2
    else:
        return 1

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
# SIZE
# =========================
def size_calc(symbol, balance, price):
    global martingale_level

    base = balance * 0.05 / price

    multiplier = {1:1, 2:1.5, 3:2}

    size = base * multiplier[martingale_level]

    if size < 0.01:
        size = 0.01

    return float(exchange.amount_to_precision(symbol, size))

# =========================
# POSICIÓN
# =========================
def get_position(symbol):
    try:
        positions = exchange.fetch_positions([symbol])
        for p in positions:
            if float(p['contracts']) > 0:
                return p
    except:
        pass
    return None

# =========================
# GESTIÓN
# =========================
def manage_position(symbol, pos):
    global martingale_level, loss_streak

    entry = float(pos['entryPrice'])
    mark = float(pos['markPrice'])
    size = float(pos['contracts'])
    side = pos['side']

    pnl = (mark - entry) * size if side == "long" else (entry - mark) * size
    exit_side = "sell" if side == "long" else "buy"

    # 🔥 cierre inmediato
    if pnl > 0:
        exchange.create_order(
            symbol=symbol,
            type="market",
            side=exit_side,
            amount=size,
            params={"tdMode": "isolated"}
        )

        print(f"💰 PROFIT {pnl:.2f}")
        martingale_level = 1
        loss_streak = 0

    elif pnl < -1:
        loss_streak += 1

        if martingale_level < MAX_MARTINGALE:
            martingale_level += 1
        else:
            martingale_level = 1

# =========================
# SEÑAL
# =========================
def signal(df):
    last = df.iloc[-1]

    if abs(last['ema20'] - last['ema50']) < last['atr'] * 0.3:
        return None

    return "buy" if last['ema20'] > last['ema50'] else "sell"

# =========================
# RIESGO
# =========================
def risk_control(balance):
    global start_balance

    if start_balance is None:
        start_balance = balance

    dd = (start_balance - balance) / start_balance

    return dd < MAX_DRAWDOWN

# =========================
# LOOP
# =========================
def run():
    global loss_streak

    print("🔥 BOT SUPREMO ACTIVADO")

    while True:
        try:
            balance = exchange.fetch_balance()['USDT']['free']

            if not risk_control(balance):
                print("🛑 STOP GLOBAL")
                break

            if loss_streak >= MAX_LOSS_STREAK:
                print("🛑 PAUSA POR PÉRDIDAS")
                time.sleep(PAUSE_TIME)
                loss_streak = 0
                continue

            symbol = choose_symbol()

            if symbol is None:
                time.sleep(20)
                continue

            df = get_data(symbol)

            if not market_ok(df):
                print("⏸ Mercado no válido")
                time.sleep(15)
                continue

            price = df['close'].iloc[-1]
            atr = df['atr'].iloc[-1]

            lev = dynamic_leverage(atr, price)
            set_leverage(symbol, lev)

            pos = get_position(symbol)

            if pos:
                manage_position(symbol, pos)
            else:
                side = signal(df)

                if side is None:
                    time.sleep(10)
                    continue

                size = size_calc(symbol, balance, price)

                exchange.create_order(
                    symbol=symbol,
                    type="market",
                    side=side,
                    amount=size,
                    params={"tdMode": "isolated"}
                )

                print(f"🚀 ENTRY {symbol} {side}")

            time.sleep(COOLDOWN)

        except Exception as e:
            print(f"❌ ERROR: {e}")
            time.sleep(5)

if __name__ == "__main__":
    run()