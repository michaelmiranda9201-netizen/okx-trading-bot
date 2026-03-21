import time
import os
import joblib
import numpy as np
import pandas as pd
import requests

from sklearn.ensemble import RandomForestClassifier

from strategy import add_indicators, rules_signal
from ensemble import ensemble_signal

# =============================
# CONFIG
# =============================
MODEL_PATH = "models/ml_model.pkl"
SYMBOL = "BTC-USDT-SWAP"

# =============================
# SIMULACIÓN
# =============================
balance = 50
position = None
entry_price = 0

# =============================
# CREAR CARPETA MODELS
# =============================
if not os.path.exists("models"):
    os.makedirs("models")

# =============================
# CARGAR O CREAR MODELO ML
# =============================
if os.path.exists(MODEL_PATH):
    print("✅ Cargando modelo ML existente...")
    ml_model = joblib.load(MODEL_PATH)
else:
    print("⚠️ Modelo no encontrado, creando uno nuevo...")
    ml_model = RandomForestClassifier()

    X = np.random.rand(20, 3)
    y = np.random.choice([-1, 0, 1], size=20)

    ml_model.fit(X, y)
    joblib.dump(ml_model, MODEL_PATH)

# =============================
# LSTM DESACTIVADO
# =============================
def lstm_signal():
    return 0

# =============================
# DATOS REALES OKX
# =============================
def get_data():
    url = f"https://www.okx.com/api/v5/market/candles?instId={SYMBOL}&bar=1m&limit=100"

    res = requests.get(url).json()
    data = res["data"]

    df = pd.DataFrame(data, columns=[
        "time","open","high","low","close","volume",
        "volCcy","volCcyQuote","confirm"
    ])

    df["close"] = df["close"].astype(float)
    df["high"] = df["high"].astype(float)
    df["low"] = df["low"].astype(float)

    return df[::-1]

# =============================
# SIMULACIÓN DE TRADE
# =============================
def simulate_trade(signal, price):
    global balance, position, entry_price

    if position is None:
        position = signal
        entry_price = price
        print(f"🟢 Trade abierto {signal.upper()} en {price}")

    else:
        if position == "buy":
            profit = price - entry_price
        else:
            profit = entry_price - price

        balance += profit

        print(f"🔴 Trade cerrado | Profit: {profit:.2f}")
        print(f"💰 Balance: {balance:.2f}")

        position = None

# =============================
# LOOP PRINCIPAL
# =============================
while True:
    try:
        df = get_data()
        df = add_indicators(df)

        last = df.iloc[-1]

        features = [[
            last["ema50"],
            last["ema200"],
            last["rsi"]
        ]]

        ml = ml_model.predict(features)[0]
        rules = rules_signal(df)
        lstm = lstm_signal()

        signal = ensemble_signal(ml, lstm, rules)

        print("-----")
        print(f"ML: {ml} | REGLAS: {rules} | LSTM: {lstm}")
        print(f"📊 SEÑAL: {signal}")

        price = last["close"]

        if signal:
            simulate_trade(signal, price)

        time.sleep(15)

    except Exception as e:
        print("❌ Error:", e)
        time.sleep(5)