import asyncio
import json
import time
import hmac
import base64
import hashlib
import aiohttp
import websockets
import numpy as np

API_KEY="db75d70b-f577-40e5-b06c-60b9c87584a7"
SECRET="DD0B0C2024162F50F4267C1D59C4AC81"
PASSPHRASE="WXcv8089@"

capital=50
fee=0.001
trade_ratio=0.99

orderbooks={}
spread_memory=[]

triangles=[
    ("BTC-USDT","ETH-BTC","ETH-USDT"),
    ("BTC-USDT","SOL-BTC","SOL-USDT")
]

# ---------- IA ENGINE ----------

def ai_predict(spread,depth,velocity):

    score=0

    if spread>0.001:
        score+=2

    if spread>0.002:
        score+=3

    if depth>3:
        score+=2

    if velocity>0:
        score+=2

    if len(spread_memory)>5:
        if spread>np.mean(spread_memory[-5:]):
            score+=2

    return score

# ---------- ORDERBOOK WS ----------

async def ws_orderbook():

    uri="wss://ws.okx.com:8443/ws/v5/public"

    async with websockets.connect(uri) as ws:

        subs=[]

        for t in triangles:
            for s in t:
                subs.append({"channel":"books5","instId":s})

        await ws.send(json.dumps({"op":"subscribe","args":subs}))

        while True:

            msg=json.loads(await ws.recv())

            if "data" in msg:

                inst=msg["arg"]["instId"]
                ob=msg["data"][0]

                bid=float(ob["bids"][0][0])
                bid_vol=float(ob["bids"][0][1])

                ask=float(ob["asks"][0][0])
                ask_vol=float(ob["asks"][0][1])

                orderbooks[inst]=(bid,bid_vol,ask,ask_vol)

# ---------- EXECUTION ENGINE ----------

def sign(ts,method,path,body=""):
    msg=str(ts)+method+path+body
    mac=hmac.new(bytes(SECRET,'utf-8'),bytes(msg,'utf-8'),hashlib.sha256)
    return base64.b64encode(mac.digest()).decode()

async def place(session,symbol,side,sz,px):

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

    async with session.post("https://www.okx.com"+path,data=body,headers=headers) as r:
        return await r.text()

# ---------- ARBITRAGE ENGINE ----------

def calc(a1,a2,b3):
    gross=(1/a1)*(1/a2)*b3
    net=gross*(1-fee)**3
    return net-1

async def arbitrage():

    global capital

    async with aiohttp.ClientSession() as session:

        while True:

            try:

                for t in triangles:

                    if not all(s in orderbooks for s in t):
                        continue

                    b1,v1,a1,av1=orderbooks[t[0]]
                    b2,v2,a2,av2=orderbooks[t[1]]
                    b3,v3,a3,av3=orderbooks[t[2]]

                    spread=calc(a1,a2,b3)

                    spread_memory.append(spread)

                    depth=(av1+av2+v3)/3

                    velocity=spread-(spread_memory[-2] if len(spread_memory)>2 else 0)

                    score=ai_predict(spread,depth,velocity)

                    print(t,"Spread",spread*100,"Score",score)

                    if score>=7:

                        trade=capital*trade_ratio

                        btc=trade/a1
                        eth=btc/a2

                        await place(session,t[0],"buy",btc,a1*0.999)
                        await place(session,t[1],"buy",eth,a2*0.999)
                        await place(session,t[2],"sell",eth,b3*1.001)

                        gain=trade*spread
                        capital+=gain

                        print("☠️ MONSTER ARBITRAJE")
                        print("Capital:",capital)

                await asyncio.sleep(0.03)

            except Exception as e:
                print("Error",e)
                await asyncio.sleep(1)

async def main():

    await asyncio.gather(
        ws_orderbook(),
        arbitrage()
    )

asyncio.run(main())