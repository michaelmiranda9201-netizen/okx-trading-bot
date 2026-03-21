import time
import joblib
import numpy as np
from tensorflow.keras.models import load_model
from strategy import add_indicators, rules_signal
from ensemble import ensemble_signal

ml_model = joblib.load("models/ml_model.pkl")
lstm_model = load_model("models/lstm_model.h5")

def get_fake_data():
    import pandas as pd
    return pd.DataFrame({"close":[1,2,3,4,5]*20})

while True:
    try:
        df = get_fake_data()
        df = add_indicators(df)

        features = [df.iloc[-1][["ema50","ema200","rsi"]]]
        sequence = np.random.rand(1,50,1)

        ml = ml_model.predict(features)[0]
        lstm = lstm_model.predict(sequence)[0][0]
        rules = rules_signal(df)

        signal = ensemble_signal(ml, lstm, rules)

        print("Signal:", signal)

        time.sleep(10)

    except Exception as e:
        print("Error:", e)