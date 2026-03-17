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

TIMEFRAME = '1m'
RISK_PER_TRADE = 0.05
GRID_LEVELS = 3

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
        'defaultMarginMode': 'isolated'  # 🔥 FORZAR AISLADO
    }
})

# =========================
# 📊 DATA
# =========================
def get_data(symbol):
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=100)
    df = pd.DataFrame(ohlcv, columns=['time','open','high','low','close','volume'])
    df['ema20'] = df['close'].ewm(span=20).mean()
    df['ema50'] = df['close'].ewm(span=50).mean()
    df['atr'] = (df['high'] - df['low']).rolling(14).mean()
    return df

def trend(df):
    return "buy" if df['ema20'].iloc[-1] > df['ema50'].iloc[-1] else "sell"

# =========================
# ⚙️ LEVERAGE DINÁMICO REAL
# =========================
def dynamic_leverage(atr, price):
    vol = atr / price

    if vol < 0.002:
        return 10
    elif vol < 0.005:
        return 7
    elif vol < 0.01:
        return 5
    else:
        return 3

def set_leverage(symbol, leverage):
    try:
        market = exchange.market(symbol)

        exchange.set_leverage(
            leverage,
            market['id'],
            params={"mgnMode": "isolated"}
        )

        print(f"⚙️ {symbol} → Leverage x{leverage} AISLADO")

    except Exception as e:
        print(f"❌ Error leverage: {e}")

# =========================
# 💰 BALANCE
# =========================
def get_balance():
    return exchange.fetch_balance()['USDT']['free']

# =========================
# 📏 SIZE OKX CORRECTO
# =========================
def calculate_size(symbol, balance, price, leverage):
    risk = balance * RISK_PER_TRADE
    position_value = risk * leverage

    size = position_value / price

    if size < 0.01:
        size = 0.01

    return float(exchange.amount_to_precision(symbol, size))

# =========================
# 📊 POSICIONES
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
# 🧹 CANCELAR ÓRDENES
# =========================
def cancel_orders(symbol):
    try:
        orders = exchange.fetch_open_orders(symbol)
        for o in orders:
            exchange.cancel_order(o['id'], symbol)
    except:
        pass

# =========================
# 📈 GRID INTELIGENTE
# =========================
def create_grid(price, atr, side):
    spacing = atr * 0.5
    levels = []

    for i in range(1, GRID_LEVELS + 1):
        if side == "buy":
            levels.append(price - spacing * i)
        else:
            levels.append(price + spacing * i)

    return levels

def place_grid(symbol, levels, size):
    try:
        for price in levels:
            side = "buy" if price < levels[0] else "sell"

            print(f"📌 GRID {symbol} | {side.upper()} | {price:.2f}")

            exchange.create_order(
                symbol=symbol,
                type="limit",
                side=side,
                amount=size,
                price=price,
                params={"tdMode": "isolated"}  # 🔥 AISLADO
            )
    except Exception as e:
        print(f"❌ Grid error: {e}")

# =========================
# 🎯 TP / SL PROFESIONAL
# =========================
def manage_position(symbol, position, atr):
    try:
        entry = float(position['entryPrice'])
        size = float(position['contracts'])
        side = position['side']

        if side == "long":
            tp = entry + atr * 1.5
            sl = entry - atr * 2
            exit_side = "sell"
        else:
            tp = entry - atr * 1.5
            sl = entry + atr * 2
            exit_side = "buy"

        print(f"🎯 {symbol} TP: {tp:.2f} | SL: {sl:.2f}")

        # TAKE PROFIT
        exchange.create_order(
            symbol=symbol,
            type="trigger",
            side=exit_side,
            amount=size,
            price=tp,
            params={
                "triggerPx": tp,
                "tdMode": "isolated"
            }
        )

        # STOP LOSS
        exchange.create_order(
            symbol=symbol,
            type="trigger",
            side=exit_side,
            amount=size,
            price=sl,
            params={
                "triggerPx": sl,
                "tdMode": "isolated"
            }
        )

    except Exception as e:
        print(f"❌ TP/SL error: {e}")

# =========================
# 🔁 BOT LOOP
# =========================
def run():
    print("🚀 BOT GRID PRO | OKX FUTUROS AISLADO")

    while True:
        try:
            balance = get_balance()
            print(f"\n💰 Balance: {balance:.2f} USDT")

            for symbol in SYMBOLS:

                df = get_data(symbol)
                price = df['close'].iloc[-1]
                atr = df['atr'].iloc[-1]
                side = trend(df)
                leverage = dynamic_leverage(atr, price)

                print(f"\n📊 {symbol}")
                print(f"Precio: {price}")
                print(f"Tendencia: {side}")
                print(f"Leverage dinámico: x{leverage}")

                set_leverage(symbol, leverage)

                size = calculate_size(symbol, balance, price, leverage)

                position = get_position(symbol)

                if position:
                    print("✅ Posición activa")
                    manage_position(symbol, position, atr)
                else:
                    print("📈 Nuevo GRID")
                    cancel_orders(symbol)
                    grid = create_grid(price, atr, side)
                    place_grid(symbol, grid, size)

            time.sleep(60)

        except Exception as e:
            print(f"❌ ERROR GENERAL: {e}")
            time.sleep(30)

# =========================
# ▶️ START
# =========================
if __name__ == "__main__":
    run()