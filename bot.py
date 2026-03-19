import ccxt
import time
import pandas as pd

# =========================
# CONFIG
# =========================
API_KEY = "db75d70b-f577-40e5-b06c-60b9c87584a7"
API_SECRET = "DD0B0C2024162F50F4267C1D59C4AC81"
PASSPHRASE = "WXcv8089@"

SYMBOL = "BTC/USDT:USDT"

MAX_DRAWDOWN = 0.1
COOLDOWN = 8

# martingala
martingale_level = 1
MAX_MARTINGALE = 3

# control
loss_streak = 0
MAX_LOSS_STREAK = 3
PAUSE_TIME = 120  # segundos

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
# DATA
# =========================
def get_data():
    ohlcv = exchange.fetch_ohlcv(SYMBOL, timeframe='1m', limit=100)
    df = pd.DataFrame(ohlcv, columns=['time','open','high','low','close','volume'])

    df['ema20'] = df['close'].ewm(span=20).mean()
    df['ema50'] = df['close'].ewm(span=50).mean()
    df['atr'] = (df['high'] - df['low']).rolling(14).mean()

    return df

# =========================
# FILTRO MERCADO
# =========================
def market_ok(df):
    atr = df['atr'].iloc[-1]
    price = df['close'].iloc[-1]

    vol = atr / price

    if vol < 0.0015:
        print("⏸ Mercado muerto")
        return False

    return True

# =========================
# LEVERAGE DINÁMICO (MAX 3)
# =========================
def dynamic_leverage(atr, price):
    vol = atr / price

    if vol < 0.002:
        return 3
    elif vol < 0.005:
        return 2
    else:
        return 1

def set_leverage(lev):
    try:
        exchange.set_leverage(
            lev,
            exchange.market(SYMBOL)['id'],
            params={"mgnMode": "isolated"}
        )
    except:
        pass

# =========================
# SIZE
# =========================
def size_calc(balance, price):
    global martingale_level

    base = balance * 0.05 / price

    multiplier = {
        1: 1,
        2: 1.5,
        3: 2
    }

    size = base * multiplier[martingale_level]

    if size < 0.01:
        size = 0.01

    return float(exchange.amount_to_precision(SYMBOL, size))

# =========================
# POSICIÓN
# =========================
def get_position():
    try:
        positions = exchange.fetch_positions([SYMBOL])
        for p in positions:
            if float(p['contracts']) > 0:
                return p
    except:
        pass
    return None

# =========================
# GESTIÓN PRO
# =========================
def manage_position(pos):
    global martingale_level, loss_streak

    entry = float(pos['entryPrice'])
    mark = float(pos['markPrice'])
    size = float(pos['contracts'])
    side = pos['side']

    pnl = (mark - entry) * size if side == "long" else (entry - mark) * size

    exit_side = "sell" if side == "long" else "buy"

    # 💰 PROFIT
    if pnl > 0:
        exchange.create_order(
            symbol=SYMBOL,
            type="market",
            side=exit_side,
            amount=size,
            params={"tdMode": "isolated"}
        )

        print(f"💰 PROFIT {pnl:.2f}")
        martingale_level = 1
        loss_streak = 0

    # ❌ PÉRDIDA
    elif pnl < -1:
        loss_streak += 1

        if martingale_level < MAX_MARTINGALE:
            martingale_level += 1
        else:
            martingale_level = 1

        print(f"⚠️ Loss streak: {loss_streak}")

# =========================
# SEÑAL MEJORADA
# =========================
def signal(df):
    last = df.iloc[-1]

    # evitar ruido
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

    if dd >= MAX_DRAWDOWN:
        print("🛑 STOP GLOBAL")
        return False

    return True

# =========================
# LOOP
# =========================
def run():
    global loss_streak

    print("🔥 BOT FINAL REAL ACTIVADO")

    while True:
        try:
            balance = exchange.fetch_balance()['USDT']['free']

            if not risk_control(balance):
                break

            df = get_data()

            if not market_ok(df):
                time.sleep(20)
                continue

            if loss_streak >= MAX_LOSS_STREAK:
                print("🛑 DEMASIADAS PÉRDIDAS → PAUSA")
                time.sleep(PAUSE_TIME)
                loss_streak = 0
                continue

            price = df['close'].iloc[-1]
            atr = df['atr'].iloc[-1]

            lev = dynamic_leverage(atr, price)
            set_leverage(lev)

            pos = get_position()

            if pos:
                manage_position(pos)
            else:
                side = signal(df)

                if side is None:
                    time.sleep(10)
                    continue

                size = size_calc(balance, price)

                exchange.create_order(
                    symbol=SYMBOL,
                    type="market",
                    side=side,
                    amount=size,
                    params={"tdMode": "isolated"}
                )

                print(f"🚀 ENTRY {side}")

            time.sleep(COOLDOWN)

        except Exception as e:
            print(f"❌ ERROR: {e}")
            time.sleep(5)

if __name__ == "__main__":
    run()