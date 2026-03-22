import asyncio
import json
import time
import hmac
import base64
import hashlib
import aiohttp
import websockets

API_KEY = "db75d70b-f577-40e5-b06c-60b9c87584a7"
SECRET = "DD0B0C2024162F50F4267C1D59C4AC81"
PASSPHRASE = "WXcv8089@"

BASE_URL = "https://www.okx.com"

capital = 50
trade_ratio = 0.98
fee = 0.001

triangles = [
    ("BTC-USDT","ETH-BTC","ETH-USDT"),
]

prices = {}

def sign(timestamp, method, request_path, body=""):
    message = str(timestamp) + method + request_path + body
    mac = hmac.new(bytes(SECRET,'utf-8'), bytes(message,'utf-8'), hashlib.sha256)
    d = mac.digest()
    return base64.b64encode(d)

async def place_order(session, symbol, side, size, price):

    path = "/api/v5/trade/order"

    body = json.dumps({
        "instId": symbol,
        "tdMode": "cash",
        "side": side,
        "ordType": "limit",
        "px": str(price),
        "sz": str(size)
    })

    ts = str(time.time())

    headers = {
        "OK-ACCESS-KEY": API_KEY,
        "OK-ACCESS-SIGN": sign(ts,"POST",path,body),
        "OK-ACCESS-TIMESTAMP": ts,
        "OK-ACCESS-PASSPHRASE": PASSPHRASE,
        "Content-Type":"application/json"
    }

    async with session.post(BASE_URL+path,data=body,headers=headers) as r:
        return await r.text()

def calc_spread(a1,a2,b3):
    gross = (1/a1)*(1/a2)*b3
    net = gross*(1-fee)**3
    return net - 1

async def websocket_prices():

    uri = "wss://ws.okx.com:8443/ws/v5/public"

    async with websockets.connect(uri) as ws:

        sub = {
            "op":"subscribe",
            "args":[
                {"channel":"tickers","instId":"BTC-USDT"},
                {"channel":"tickers","instId":"ETH-BTC"},
                {"channel":"tickers","instId":"ETH-USDT"}
            ]
        }

        await ws.send(json.dumps(sub))

        while True:

            msg = await ws.recv()
            data = json.loads(msg)

            if "data" in data:
                inst = data["arg"]["instId"]
                prices[inst] = float(data["data"][0]["last"])

async def arbitrage():

    global capital

    async with aiohttp.ClientSession() as session:

        while True:

            try:

                if len(prices) < 3:
                    await asyncio.sleep(0.2)
                    continue

                p1 = prices["BTC-USDT"]
                p2 = prices["ETH-BTC"]
                p3 = prices["ETH-USDT"]

                spread = calc_spread(p1,p2,p3)

                if spread > 0.0015:

                    trade_amount = capital * trade_ratio

                    btc_size = trade_amount / p1
                    eth_size = btc_size / p2

                    await place_order(session,"BTC-USDT","buy",btc_size,p1)
                    await place_order(session,"ETH-BTC","buy",eth_size,p2)
                    await place_order(session,"ETH-USDT","sell",eth_size,p3)

                    gain = trade_amount * spread
                    capital += gain

                    print("🚀 ARBITRAJE REAL EJECUTADO")
                    print("Capital:",capital)

                await asyncio.sleep(0.05)

            except Exception as e:
                print("Error",e)
                await asyncio.sleep(1)

async def main():
    await asyncio.gather(
        websocket_prices(),
        arbitrage()
    )

asyncio.run(main())