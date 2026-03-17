import ccxt
import time
import numpy as np
import pandas as pd

# =========================
# 🔐 CONFIGURACIÓN
# =========================
API_KEY = "db75d70b-f577-40e5-b06c-60b9c87584a7"
API_SECRET = "DD0B0C2024162F50F4267C1D59C4AC81"
PASSPHRASE = "WXcv8089@"

SYMBOLS = ["BTC/USDT:USDT", "ETH/USDT:USDT"]

TIMEFRAME = '1m'
RISK_PER_TRADE = 0.05
GRID_LEVELS = 3
LEVERAGE_MAX = 10

# =========================
# 🔌 CONEXIÓN OKX
# =========================
exchange = ccxt.okx({
    'apiKey': API_KEY,
    'secret': API_SECRET,
    'password': PASSPHRASE,
    'enableRateLimit': True,
    'options': {'defaultType': 'swap'}
})

# =========================
# 📊 FUNCIONES
# =========================

def get_balance():
    balance = exchange.fetch_balance()
    return balance['USDT']['free']

def get_data(symbol):
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=100)
    df = pd.DataFrame(ohlcv, columns=['time','open','high','low','close','volume'])
    return df

def indicators(df):
    df['ema20'] = df['close'].ewm(span=20).mean()
    df['ema50'] = df['close'].ewm(span=50).mean()
    df['atr'] = (df['high'] - df['low']).rolling(14).mean()
    return df

def trend(df):
    return "buy" if df['ema20'].iloc[-1] > df['ema50'].iloc[-1] else "sell"

def dynamic_leverage(atr, price):
    vol = atr / price
    lev = int(min(max(3, 1/vol), LEVERAGE_MAX))
    return lev

# =========================
# 💰 TAMAÑO CORRECTO OKX
# =========================

def calculate_size(symbol, balance, price, leverage):
    risk = balance * RISK_PER_TRADE
    position_value = risk * leverage

    size = position_value / price

    min_size = 0.01
    if size < min_size:
        size = min_size

    size = float(exchange.amount_to_precision(symbol, size))
    return size

# =========================
# 🧹 LIMPIAR ÓRDENES
# =========================

def cancel_orders(symbol):
    try:
        orders = exchange.fetch_open_orders(symbol)
        for o in orders:
            exchange.cancel_order(o['id'], symbol)
    except:
        pass

# =========================
# 📈 CREAR GRID
# =========================

def create_grid(symbol, price, atr, side, balance, leverage):
    orders = []
    spacing = atr * 0.5

    size = calculate_size(symbol, balance, price, leverage)

    if size < 0.01:
        print(f"⚠️ Tamaño muy pequeño {symbol}")
        return []

    for i in range(1, GRID_LEVELS + 1):

        if side == "buy":
            entry = price - spacing * i
            tp = entry + spacing * 1.5
            sl = entry - atr * 2

            orders.append((entry, tp, sl, "buy"))

        else:
            entry = price + spacing * i
            tp = entry - spacing * 1.5
            sl = entry + atr * 2

            orders.append((entry, tp, sl, "sell"))

    return orders, size

# =========================
# 🚀 EJECUTAR ÓRDENES
# =========================

def place_orders(symbol, orders, size, leverage):
    try:
        exchange.set_leverage(leverage, symbol)

        for entry, tp, sl, side in orders:

            print(f"📌 {symbol} | {side.upper()} | Entry: {entry:.2f} | Size: {size}")

            exchange.create_order(
                symbol=symbol,
                type="limit",
                side=side,
                amount=size,
                price=entry,
                params={
                    "tdMode": "cross",
                    "tpTriggerPx": str(tp),
                    "tpOrdPx": str(tp),
                    "slTriggerPx": str(sl),
                    "slOrdPx": str(sl)
                }
            )

    except Exception as e:
        print(f"❌ Error orden: {e}")

# =========================
# 🔁 BOT LOOP
# =========================

def run():
    print("🚀 BOT GRID FUTUROS OKX INICIADO")

    while True:
        try:
            balance = get_balance()
            print(f"\n💰 Balance: {balance:.2f} USDT")

            for symbol in SYMBOLS:
                df = get_data(symbol)
                df = indicators(df)

                price = df['close'].iloc[-1]
                atr = df['atr'].iloc[-1]
                side = trend(df)
                leverage = dynamic_leverage(atr, price)

                print(f"\n📊 {symbol}")
                print(f"Precio: {price}")
                print(f"Tendencia: {side}")
                print(f"Leverage: x{leverage}")

                # 🧹 limpiar grid viejo
                cancel_orders(symbol)

                # 📈 crear nuevo grid
                grid, size = create_grid(symbol, price, atr, side, balance, leverage)

                # 🚀 ejecutar
                place_orders(symbol, grid, size, leverage)

            time.sleep(60)

        except Exception as e:
            print(f"❌ ERROR GENERAL: {e}")
            time.sleep(30)

# =========================
# ▶️ START
# =========================

if __name__ == "__main__":
    run()