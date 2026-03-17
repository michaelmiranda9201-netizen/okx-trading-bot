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
RISK_PER_TRADE = 0.05  # 5% del balance
LEVERAGE_MAX = 10
GRID_LEVELS = 5

# =========================
# 🔌 CONEXIÓN OKX
# =========================
exchange = ccxt.okx({
    'apiKey': API_KEY,
    'secret': API_SECRET,
    'password': PASSPHRASE,
    'enableRateLimit': True,
    'options': {
        'defaultType': 'swap'
    }
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

def calculate_indicators(df):
    df['ema_fast'] = df['close'].ewm(span=20).mean()
    df['ema_slow'] = df['close'].ewm(span=50).mean()
    df['atr'] = (df['high'] - df['low']).rolling(14).mean()
    return df

def get_trend(df):
    if df['ema_fast'].iloc[-1] > df['ema_slow'].iloc[-1]:
        return "bullish"
    else:
        return "bearish"

def calculate_leverage(atr, price):
    vol = atr / price
    lev = int(min(max(2, 1 / vol), LEVERAGE_MAX))
    return lev

def calculate_position_size(balance, price):
    risk_amount = balance * RISK_PER_TRADE
    size = risk_amount / price
    return size

# =========================
# 📈 GRID DINÁMICO
# =========================

def create_grid_orders(symbol, price, atr, trend, balance):
    grid_spacing = atr * 0.5
    orders = []

    size = calculate_position_size(balance, price)

    for i in range(1, GRID_LEVELS + 1):
        if trend == "bullish":
            buy_price = price - (grid_spacing * i)
            tp = price + (grid_spacing * i)
            sl = price - (atr * 2)

            orders.append({
                'side': 'buy',
                'price': buy_price,
                'tp': tp,
                'sl': sl,
                'size': size
            })

        else:
            sell_price = price + (grid_spacing * i)
            tp = price - (grid_spacing * i)
            sl = price + (atr * 2)

            orders.append({
                'side': 'sell',
                'price': sell_price,
                'tp': tp,
                'sl': sl,
                'size': size
            })

    return orders

# =========================
# 🚀 EJECUCIÓN DE ÓRDENES
# =========================

def place_orders(symbol, orders, leverage):
    try:
        exchange.set_leverage(leverage, symbol)

        for order in orders:
            side = order['side']
            price = order['price']
            size = order['size']

            print(f"📌 {symbol} | {side.upper()} | Precio: {price:.2f} | Size: {size:.6f}")

            exchange.create_limit_order(
                symbol=symbol,
                side=side,
                amount=size,
                price=price,
                params={
                    "tdMode": "cross"
                }
            )

    except Exception as e:
        print(f"❌ Error orden: {e}")

# =========================
# 🔁 LOOP PRINCIPAL
# =========================

def run_bot():
    while True:
        try:
            balance = get_balance()
            print(f"\n💰 Balance: {balance:.2f} USDT")

            for symbol in SYMBOLS:
                df = get_data(symbol)
                df = calculate_indicators(df)

                price = df['close'].iloc[-1]
                atr = df['atr'].iloc[-1]
                trend = get_trend(df)

                leverage = calculate_leverage(atr, price)

                print(f"\n📊 {symbol}")
                print(f"Precio: {price}")
                print(f"Tendencia: {trend}")
                print(f"Leverage: x{leverage}")

                orders = create_grid_orders(symbol, price, atr, trend, balance)

                place_orders(symbol, orders, leverage)

            # Espera 60 segundos
            time.sleep(60)

        except Exception as e:
            print(f"❌ Error general: {e}")
            time.sleep(30)

# =========================
# ▶️ START
# =========================

if __name__ == "__main__":
    run_bot()