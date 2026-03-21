import pandas as pd
from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator

def add_indicators(df):
    df["ema50"] = EMAIndicator(df["close"], 50).ema_indicator()
    df["ema200"] = EMAIndicator(df["close"], 200).ema_indicator()
    df["rsi"] = RSIIndicator(df["close"], 14).rsi()
    return df

def rules_signal(df):
    last = df.iloc[-1]

    if last["ema50"] > last["ema200"] and last["rsi"] > 55:
        return 1
    elif last["ema50"] < last["ema200"] and last["rsi"] < 45:
        return -1
    return 0