import asyncio
import time
import json
import os
import hmac
import base64
import hashlib
import websockets
import aiohttp

# ================= VARIABLES =================
API_KEY = os.getenv("db75d70b-f577-40e5-b06c-60b9c87584a7")
SECRET = os.getenv("DD0B0C2024162F50F4267C1D59C4AC81")
PASSPHRASE = os.getenv("WXcv8089@")
INITIAL_CAPITAL = float(os.getenv("INITIAL_CAPITAL", 50))

# ================= FLAGS =================
REAL_TRADING = all([API_KEY, SECRET, PASSPHRASE])
if not REAL_TRADING:
    raise Exception("❌ Faltan variables de entorno: API_KEY, SECRET o PASSPHRASE")

fee = 0.001
trade_ratio = 0.95

orderbooks = {}
spread_memory = []

# ================= FUNCIONES =================
def sign(ts, method, path, body=""):
    msg = str(ts) + method + path + (body if body else "")
    mac = hmac.new(SECRET.encode(), msg.encode(), hashlib.sha256)
    return base64.b64encode(mac.digest()).decode()

async def place(session, symbol, side, sz, px):
    # Redondeo según mínimo de OKX
    sz = max(0.0001, round(sz, 6))  # 6 decimales para cripto
    px = round(px, 2)               # precio 2 decimales USDT

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
        async with session.post("https://www.okx.com"+path, data=body_json, headers=headers) as r:
            txt = await r.text()
            print("ORDER:", txt)
    except Exception as e:
        print("ORDER ERROR:", e)

def calc_triangular(a1,a2):
    gross = a1 / a2
    net = gross * (1 - fee)**2
    return net - 1

def ai_score(spread, depth, velocity):
    score = 0
    if spread > 0.0005: score += 2
    if spread > 0.001: score += 2
    if depth > 2: score += 1
    if velocity > 0: score += 1
    return score

# ================= WEBSOCKET =================
async def ws_loop():
    global orderbooks
    uri = "wss://ws.okx.com:8443/ws/v5/public"
    subs = [
        {"channel":"books5","instId":"BTC-USDT"},
        {"channel":"books5","instId":"ETH-USDT"},
        {"channel":"books5","instId":"SOL-USDT"},
    ]
    while True:
        try:
            async with websockets.connect(uri, ping_interval=20, ping_timeout=20) as ws:
                await ws.send(json.dumps({"op":"subscribe","args":subs}))
                print("✅ WS CONNECTED")
                while True:
                    msg = await ws.recv()
                    data = json.loads(msg)
                    if "data" in data:
                        inst = data["arg"]["instId"]
                        ob = data["data"][0]
                        bid, bid_vol = float(ob["bids"][0][0]), float(ob["bids"][0][1])
                        ask, ask_vol = float(ob["asks"][0][0]), float(ob["asks"][0][1])
                        orderbooks[inst] = (bid,bid_vol,ask,ask_vol)
        except Exception as e:
            print("WS ERROR:", e)
            await asyncio.sleep(5)

# ================= ARBITRAGE =================
async def arbitrage_loop():
    global capital, spread_memory
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                triangles = [
                    ("BTC-USDT","ETH-USDT"),
                    ("BTC-USDT","SOL-USDT"),
                ]
                for t in triangles:
                    if all(p in orderbooks for p in t):
                        b1,v1,a1,av1 = orderbooks[t[0]]
                        b2,v2,a2,av2 = orderbooks[t[1]]

                        # Validar precios
                        if a1 <=0 or a2 <=0:
                            print(f"⚠️ Precio inválido: a1={a1}, a2={a2}. Saltando trade.")
                            continue

                        spread = calc_triangular(a1,a2)
                        depth = (av1+av2)/2
                        velocity = spread - (spread_memory[-1] if spread_memory else 0)
                        score = ai_score(spread, depth, velocity)
                        spread_memory.append(spread)

                        if score >= 3:
                            trade = capital*trade_ratio
                            alt_amount = trade / a2

                            # Ejecutar órdenes reales
                            await place(session,t[0],"buy",trade,a1*0.999)
                            await place(session,t[1],"sell",alt_amount,a2*1.001)

                            gain = trade*spread
                            capital += gain
                            print(f"🚀 TRADE {t} Spread:{spread*100:.3f}% Score:{score} Capital:{capital:.2f}")
                        else:
                            print(f"Spread:{spread*100:.3f}% Score:{score}")

                await asyncio.sleep(0.05)
            except Exception as e:
                print("ARBITRAGE ERROR:", e)
                await asyncio.sleep(1)

# ================= MAIN =================
async def main():
    await asyncio.gather(
        ws_loop(),
        arbitrage_loop()
    )

asyncio.run(main())