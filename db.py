import psycopg2
import os

conn = psycopg2.connect(os.getenv("DATABASE_URL"))
cursor = conn.cursor()

def save_candle(symbol, data):
    cursor.execute("""
        INSERT INTO market_data (symbol, time, open, high, low, close, volume)
        VALUES (%s,%s,%s,%s,%s,%s,%s)
    """, data)
    conn.commit()