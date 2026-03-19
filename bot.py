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
# LEVERAGE DINÁMICO
# =========================
def dynamic_leverage(atr, price):
    vol = atr / price

    if vol < 0.002:
        return 12
    elif vol < 0.005:
        return 10
    else:
        return 7

def set_leverage(lev):
    exchange.set_leverage(
        lev,
        exchange.market(SYMBOL)['id'],
        params={"mgnMode": "isolated"}
    )

# =========================
# MARTINGALA SIZE
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
# POSICIONES
# =========================
def get_position():
    try:
        pos = exchange.fetch_positions([SYMBOL])
        for p in pos:
            if float(p['contracts']) > 0:
                return p
    except:
        pass
    return None

# =========================
# GESTIÓN
# =========================
def manage_position(pos):
    global martingale_level

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

        print(f"💰 PROFIT {pnl:.2f} | RESET MARTINGALA")
        martingale_level = 1

    # ❌ PÉRDIDA
    elif pnl < -1:
        if martingale_level < MAX_MARTINGALE:
            martingale_level += 1
            print(f"⚠️ Martingala nivel {martingale_level}")
        else:
            print("🛑 MAX MARTINGALA → RESET")
            martingale_level = 1

# =========================
# ENTRY SIMPLE
# =========================
def signal(df):
    last = df.iloc[-1]
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
    global martingale_level

    print("🔥 BOT MARTINGALA DINÁMICA ACTIVADO")

    while True:
        try:
            balance = exchange.fetch_balance()['USDT']['free']

            if not risk_control(balance):
                break

            df = get_data()

            price = df['close'].iloc[-1]
            atr = df['atr'].iloc[-1]

            lev = dynamic_leverage(atr, price)
            set_leverage(lev)

            pos = get_position()

            if pos:
                manage_position(pos)
            else:
                side = signal(df)
                size = size_calc(balance, price)

                exchange.create_order(
                    symbol=SYMBOL,
                    type="market",
                    side=side,
                    amount=size,
                    params={"tdMode": "isolated"}
                )

                print(f"🚀 ENTRY {side} | Nivel {martingale_level}")

            time.sleep(COOLDOWN)

        except Exception as e:
            print(f"❌ ERROR: {e}")
            time.sleep(5)

if __name__ == "__main__":
    run()