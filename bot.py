import asyncio
import json
import time
import os
import hmac
import base64
import hashlib
import aiohttp
import websockets
import numpy as np

API_KEY = os.getenv("db75d70b-f577-40e5-b06c-60b9c87584a7")
SECRET = os.getenv("DD0B0C2024162F50F4267C1D59C4AC81")
PASSPHRASE = os.getenv("WXcv8089@")

capital = float(os.getenv("INITIAL_CAPITAL", 50))

fee = 0.001
trade_ratio = 0.97

orderbooks = {}
spread_memory = []

triangles = [
    ("BTC-USDT","ETH-BTC","ETH-USDT"),
]

# ================= IA SCORE =================

def ai_score(spread, depth, velocity):
    score = 0
    if spread > 0.002:
        score += 4
    if spread > 0.003:
        score += 3
    if depth > 3:
        score += 2
    if velocity > 0:
        score += 2
    return score

# ================= SIGN =================

def sign(ts, method, path, body=""):
    msg = str(ts)+method+path+body
    mac = hmac.new(SECRET.encode(), msg.encode(), hashlib.sha256)
    return base64.b64encode(mac.digest()).decode()

# ================= ORDER =================

async def place(session, symbol, side, sz, px):

    path="/api/v5/trade/order"

    body=json.dumps({
        "instId":symbol,
        "tdMode":"cash",
        "side":side,
        "ordType":"limit",
        "px":str(px),
        "sz":str(sz)
    })

    ts=str(time.time())

    headers={
        "OK-ACCESS-KEY":API_KEY,
        "OK-ACCESS-SIGN":sign(ts,"POST",path,body),
        "OK-ACCESS-TIMESTAMP":ts,
        "OK-ACCESS-PASSPHRASE":PASSPHRASE,
        "Content-Type":"application/json"
    }

    try:
        async with session.post("https://www.okx.com"+path,data=body,headers=headers) as r:
            txt = await r.text()
            print("ORDER:", txt)
    except Exception as e:
        print("ORDER ERROR:", e)

# ================= SPREAD =================

def calc(a1,a2,b3):
    gross = (1/a1)*(1/a2)*b3
    net = gross*(1-fee)**3
    return net - 1

# ================= WS FEED =================

async def ws_loop():

    global orderbooks

    uri = "wss://ws.okx.com:8443/ws/v5/public"

    while True:

        try:

            async with websockets.connect(
                uri,
                ping_interval=20,
                ping_timeout=20,
                close_timeout=5
            ) as ws:

                sub = {
                    "op":"subscribe",
                    "args":[
                        {"channel":"books5","instId":"BTC-USDT"},
                        {"channel":"books5","instId":"ETH-BTC"},
                        {"channel":"books5","instId":"ETH-USDT"},
                    ]
                }

                await ws.send(json.dumps(sub))

                print("✅ WS CONNECTED")

                while True:

                    msg = await ws.recv()
                    data = json.loads(msg)

                    if "data" in data:

                        inst = data["arg"]["instId"]
                        ob = data["data"][0]

                        bid = float(ob["bids"][0][0])
                        bid_vol = float(ob["bids"][0][1])
                        ask = float(ob["asks"][0][0])
                        ask_vol = float(ob["asks"][0][1])

                        orderbooks[inst] = (bid,bid_vol,ask,ask_vol)

        except Exception as e:
            print("WS ERROR:", e)
            await asyncio.sleep(5)

# ================= ARBITRAGE =================

async def arbitrage_loop():

    global capital

    async with aiohttp.ClientSession() as session:

        while True:

            try:

                if not all(s in orderbooks for s in triangles[0]):
                    await asyncio.sleep(0.2)
                    continue

                b1,v1,a1,av1 = orderbooks["BTC-USDT"]
                b2,v2,a2,av2 = orderbooks["ETH-BTC"]
                b3,v3,a3,av3 = orderbooks["ETH-USDT"]

                spread = calc(a1,a2,b3)
                spread_memory.append(spread)

                velocity = spread - (spread_memory[-2] if len(spread_memory)>2 else 0)
                depth = (av1+av2+v3)/3

                score = ai_score(spread,depth,velocity)

                print("Spread:",round(spread*100,4),"Score:",score)

                if score >= 7:

                    trade = capital * trade_ratio

                    btc = trade / a1
                    eth = btc / a2

                    await place(session,"BTC-USDT","buy",btc,a1*0.999)
                    await place(session,"ETH-BTC","buy",eth,a2*0.999)
                    await place(session,"ETH-USDT","sell",eth,b3*1.001)

                    gain = trade * spread
                    capital += gain

                    print("🚀 CAPITAL:",capital)

                print("❤️ BOT ALIVE", time.time())

                await asyncio.sleep(0.15)

            except Exception as e:
                print("ARBITRAGE ERROR:", e)
                await asyncio.sleep(2)

# ================= MAIN =================

async def main():
    await asyncio.gather(
        ws_loop(),
        arbitrage_loop()
    )

asyncio.run(main())