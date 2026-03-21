import pandas as pd
import joblib
from sklearn.ensemble import RandomForestClassifier

def train():
    df = pd.read_csv("data/data.csv")

    X = df[["ema50", "ema200", "rsi"]]
    y = df["target"]

    model = RandomForestClassifier()
    model.fit(X, y)

    joblib.dump(model, "models/ml_model.pkl")

if __name__ == "__main__":
    train()