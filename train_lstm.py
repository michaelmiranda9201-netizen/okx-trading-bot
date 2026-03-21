import numpy as np
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense

def build_model(shape):
    model = Sequential()
    model.add(LSTM(64, return_sequences=True, input_shape=shape))
    model.add(LSTM(32))
    model.add(Dense(1, activation='tanh'))
    model.compile(optimizer='adam', loss='mse')
    return model

def train():
    X = np.load("data/X.npy")
    y = np.load("data/y.npy")

    model = build_model((X.shape[1], X.shape[2]))
    model.fit(X, y, epochs=5)

    model.save("models/lstm_model.h5")

if __name__ == "__main__":
    train()