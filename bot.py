import asyncio
import aiohttp
import time
import os
import hmac
import base64
import hashlib
import numpy as np

API_KEY = os.getenv("db75d70b-f577-40e5-b06c-60b9c87584a7")
SECRET = os.getenv("DD0B0C2024162F50F4267C1D59C4AC81")
PASSPHRASE = os.getenv("WXcv8089@")

capital = float(os.getenv("INITIAL_CAPITAL", 50))

fee = 0.001
trade_ratio = 0.95

orderbooks = {}
triangles = []
spread_memory = []

# ================= SIGN =================
def sign(ts, method, path, body=""):
    msg = str(ts) + method + path + body
    mac = hmac.new(SECRET.encode(), msg.encode(), hashlib.sha256)
    return base64.b64encode(mac.digest()).decode()

# ================= ORDER =================
async def place(session, symbol, side, sz, px):
    path = "/api/v5/trade/order"
    body = {
        "instId": symbol,
        "tdMode": "cash",
        "side": side,
        "ordType": "limit",
        "px": str(px),
        "sz": str(sz)
    }
    body_json = json.dumps(body)
    ts = str(time.time())
    headers = {
        "OK-ACCESS-KEY": API_KEY,
        "OK-ACCESS-SIGN": sign(ts, "POST", path, body_json),
        "OK-ACCESS-TIMESTAMP": ts,
        "OK-ACCESS-PASSPHRASE": PASSPHRASE,
        "Content-Type": "application/json"
    }
    try:
        async with session.post("https://www.okx.com" + path, data=body_json, headers=headers) as r:
            txt = await r.text()
            print("ORDER:", txt)
    except Exception as e:
        print("ORDER ERROR:", e)

# ================= SPREAD =================
def calc_triangular(a1, a2, b3):
    gross = (1/a1)*(1/a2)*b3
    net = gross*(1-fee)**3
    return net - 1

def ai_score(spread, depth, velocity):
    score = 0
    if spread > 0.001:
        score += 2
    if spread > 0.002:
        score += 2
    if depth > 2:
        score += 1
    if velocity > 0:
        score += 1
    return score

# ================= GET PAIRS =================
async def fetch_pairs():
    url = "https://www.okx.com/api/v5/public/instruments?instType=SPOT"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as r:
            data = await r.json()
            usdt_pairs = [d["instId"] for d in data["data"] if d["quoteCcy"]=="USDT"]
            return usdt_pairs

# ================= ORDERBOOK =================
async def fetch_orderbook(session, symbol):
    url = f"https://www.okx.com/api/v5/market/books?instId={symbol}&sz=5"
    async with session.get(url) as r:
        data = await r.json()
        if "data" not in data or len(data["data"])==0:
            return None
        d = data["data"][0]
        bid, bid_vol = float(d["bids"][0][0]), float(d["bids"][0][1])
        ask, ask_vol = float(d["asks"][0][0]), float(d["asks"][0][1])
        return bid, bid_vol, ask, ask_vol

# ================= TRIANGLES =================
def form_triangles(usdt_pairs):
    triangles_local = []
    assets = [p.split("-")[0] for p in usdt_pairs]
    for base1 in assets:
        for base2 in assets:
            if base1 != base2:
                p1 = f"{base1}-USDT" if f"{base1}-USDT" in usdt_pairs else None
                p2 = f"{base2}-{base1}" if f"{base2}-{base1}" in usdt_pairs else None
                p3 = f"{base2}-USDT" if f"{base2}-USDT" in usdt_pairs else None
                if all([p1,p2,p3]):
                    triangles_local.append((p1,p2,p3))
    return triangles_local

# ================= TRADING LOOP =================
async def trading_loop():
    global capital, triangles, orderbooks, spread_memory

    usdt_pairs = await fetch_pairs()
    triangles = form_triangles(usdt_pairs)
    print(f"✅ Triangles total: {len(triangles)}")

    async with aiohttp.ClientSession() as session:
        while True:
            try:
                # actualizar orderbooks
                for pair in set([p for t in triangles for p in t]):
                    ob = await fetch_orderbook(session, pair)
                    if ob:
                        orderbooks[pair] = ob
                # revisar triángulos
                for t in triangles:
                    if all(p in orderbooks for p in t):
                        b1,v1,a1,av1 = orderbooks[t[0]]
                        b2,v2,a2,av2 = orderbooks[t[1]]
                        b3,v3,a3,av3 = orderbooks[t[2]]

                        spread = calc_triangular(a1,a2,b3)
                        depth = (av1+av2+v3)/3
                        velocity = spread - (spread_memory[-1] if len(spread_memory)>0 else 0)
                        score = ai_score(spread, depth, velocity)

                        spread_memory.append(spread)

                        if score >= 4:
                            trade = capital * trade_ratio
                            btc = trade / a1
                            eth = btc / a2

                            # REAL ORDERS
                            await place(session, t[0], "buy", btc, a1*0.999)
                            await place(session, t[1], "buy", eth, a2*0.999)
                            await place(session, t[2], "sell", eth, b3*1.001)

                            gain = trade * spread
                            capital += gain
                            print(f"🚀 TRADE {t} Spread:{spread*100:.3f}% Score:{score} Capital:{capital:.2f}")
                        else:
                            print(f"Spread:{spread*100:.3f}% Score:{score}")
                await asyncio.sleep(0.15)
            except Exception as e:
                print("ERROR:", e)
                await asyncio.sleep(1)

# ================= MAIN =================
async def main():
    await trading_loop()

asyncio.run(main())