import time
import os
import joblib
import numpy as np
import pandas as pd

from sklearn.ensemble import RandomForestClassifier

from strategy import add_indicators, rules_signal
from ensemble import ensemble_signal

# =============================
# CONFIG
# =============================
MODEL_PATH = "models/ml_model.pkl"

# =============================
# CREAR CARPETA MODELS SI NO EXISTE
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

    # datos fake para inicializar
    X = np.random.rand(20, 3)
    y = np.random.choice([-1, 0, 1], size=20)

    ml_model.fit(X, y)

    joblib.dump(ml_model, MODEL_PATH)
    print("✅ Modelo creado y guardado")

# =============================
# LSTM DESACTIVADO (Railway friendly)
# =============================
def lstm_signal():
    return 0  # desactivado por estabilidad

# =============================
# DATA (SIMULADA POR AHORA)
# =============================
def get_data():
    # ⚠️ luego aquí conectamos OKX real
    df = pd.DataFrame({
        "close": np.random.rand(200) * 100
    })
    return df

# =============================
# LOOP PRINCIPAL
# =============================
while True:
    try:
        df = get_data()

        df = add_indicators(df)

        last = df.iloc[-1]

        # features para ML
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
        print(f"ML: {ml} | RULES: {rules} | LSTM: {lstm}")
        print(f"📊 SIGNAL: {signal}")

        time.sleep(10)

    except Exception as e:
        print("❌ Error:", e)
        time.sleep(5)