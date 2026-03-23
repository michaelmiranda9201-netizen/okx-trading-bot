import ccxt
import pandas as pd
import time
import os

# ===== CONFIG =====
API_KEY = os.getenv("db75d70b-f577-40e5-b06c-60b9c87584a7")
SECRET = os.getenv("DD0B0C2024162F50F4267C1D59C4AC81")
PASSPHRASE = os.getenv("WXcv8089@")

symbol = "SOL/USDT"
timeframe = "1m"
capital = 50
leverage = 3
base_risk = 0.01
max_trades = 3

daily_loss_limit = 0.10  # 10%

# ===== CONEXIÓN =====
exchange = ccxt.okx({
    'apiKey': API_KEY,
    'secret': SECRET,
    'password': PASSPHRASE,
    'enableRateLimit': True,
})

open_trades = 0
equity = capital

# ===== DATA =====
def get_data():
    ohlc = exchange.fetch_ohlcv(symbol, timeframe, limit=100)
    df = pd.DataFrame(ohlc, columns=['time','open','high','low','close','volume'])
    return df

# ===== INDICADORES =====
def indicators(df):
    df['ema50'] = df['close'].ewm(span=50).mean()
    df['ema200'] = df['close'].ewm(span=200).mean()

    # RSI
    delta = df['close'].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    rs = gain.rolling(14).mean() / loss.rolling(14).mean()
    df['rsi'] = 100 - (100 / (1 + rs))

    # ATR (volatilidad)
    df['tr'] = df[['high','low','close']].max(axis=1) - df[['high','low','close']].min(axis=1)
    df['atr'] = df['tr'].rolling(14).mean()

    return df

# ===== DETECCIÓN =====
def market_type(df):
    ema_diff = abs(df['ema50'].iloc[-1] - df['ema200'].iloc[-1]) / df['close'].iloc[-1]

    if ema_diff < 0.002:
        return "range"
    elif df['ema50'].iloc[-1] > df['ema200'].iloc[-1]:
        return "bull"
    else:
        return "bear"

# ===== VOLUMEN =====
def volume_filter(df):
    avg_vol = df['volume'].rolling(20).mean().iloc[-1]
    return df['volume'].iloc[-1] > avg_vol

# ===== RIESGO DINÁMICO =====
def dynamic_risk():
    global equity
    if equity < capital * 0.9:
        return base_risk * 0.5
    return base_risk

# ===== GRID =====
def grid_levels(price, atr):
    levels = []
    for i in range(1, 5):
        levels.append(price - atr * i)
    return levels

# ===== TRADING =====
def execute(df):
    global open_trades, equity

    if open_trades >= max_trades:
        return

    if equity < capital * (1 - daily_loss_limit):
        print("KILL SWITCH ACTIVADO")
        return

    price = df['close'].iloc[-1]
    rsi = df['rsi'].iloc[-1]
    atr = df['atr'].iloc[-1]
    market = market_type(df)

    if not volume_filter(df):
        return

    risk = dynamic_risk()
    amount = (capital * leverage * risk) / price

    print(f"{market} | Precio: {price} | RSI: {rsi}")

    try:
        # ===== RANGO =====
        if market == "range":
            for lvl in grid_levels(price, atr):
                exchange.create_limit_buy_order(symbol, amount, lvl)
                open_trades += 1

        # ===== TENDENCIA ALCISTA =====
        elif market == "bull" and rsi < 40:
            exchange.create_market_buy_order(symbol, amount)
            open_trades += 1

        # ===== TENDENCIA BAJISTA =====
        elif market == "bear" and rsi > 60:
            exchange.create_market_sell_order(symbol, amount)
            open_trades += 1

    except Exception as e:
        print("Error:", e)

# ===== LOOP =====
while True:
    try:
        df = get_data()
        df = indicators(df)

        execute(df)

        time.sleep(60)

    except Exception as e:
        print("Error general:", e)
        time.sleep(10)