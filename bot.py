import time, hmac, base64, hashlib, requests, pandas as pd, ta, os, json, traceback
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

API_KEY = os.getenv("db75d70b-f577-40e5-b06c-60b9c87584a7")
SECRET = os.getenv("DD0B0C2024162F50F4267C1D59C4AC81")
PASSPHRASE = os.getenv("WXcv8089@")

BASE_URL = "https://www.okx.com"
AI_FILE = "ai_trades.json"
MAX_TRADES = 3

# =========================
# 🧠 IA REAL
# =========================
def load_ai():
    if not os.path.exists(AI_FILE):
        return {"trades":[]}
    return json.load(open(AI_FILE))

def save_ai(data):
    with open(AI_FILE,"w") as f:
        json.dump(data,f,indent=2)

def log_trade(pair, result):
    data = load_ai()
    data["trades"].append({
        "pair": pair,
        "result": result,
        "time": str(datetime.utcnow())
    })
    save_ai(data)

def winrate():
    data = load_ai()
    trades = data["trades"]

    if len(trades) < 5:
        return 0.5

    wins = len([t for t in trades if t["result"] == "win"])
    return wins / len(trades)

# =========================
# 🔐 AUTH
# =========================
def sign(msg):
    return base64.b64encode(
        hmac.new(SECRET.encode(), msg.encode(), hashlib.sha256).digest()
    ).decode()

def headers(method,path,body=""):
    ts=datetime.utcnow().isoformat()+"Z"
    msg=ts+method+path+body
    return {
        "OK-ACCESS-KEY":API_KEY,
        "OK-ACCESS-SIGN":sign(msg),
        "OK-ACCESS-TIMESTAMP":ts,
        "OK-ACCESS-PASSPHRASE":PASSPHRASE,
        "Content-Type":"application/json"
    }

# =========================
# 💰 BALANCE REAL
# =========================
def get_balance():
    path="/api/v5/account/balance"
    r=requests.get(BASE_URL+path,headers=headers("GET",path)).json()

    for d in r["data"][0]["details"]:
        if d["ccy"]=="USDT":
            return float(d["availBal"])

    return 50

# =========================
# 📊 DATOS
# =========================
def get_pairs():
    data=requests.get(BASE_URL+"/api/v5/market/tickers?instType=SWAP").json()["data"]
    pairs=[]
    for x in data:
        try:
            if "USDT" not in x["instId"]:
                continue
            if float(x["volCcy24h"]) < 1000000:
                continue
            pairs.append(x["instId"])
        except:
            continue
    return pairs

def get_candles(pair):
    data=requests.get(BASE_URL+f"/api/v5/market/candles?instId={pair}&bar=1H&limit=100").json()["data"]
    df=pd.DataFrame(data,columns=["t","o","h","l","c","v","","",""])
    df["c"]=df["c"].astype(float)
    df["h"]=df["h"].astype(float)
    df["l"]=df["l"].astype(float)

    df["ema50"]=ta.trend.ema_indicator(df["c"],50)
    df["ema200"]=ta.trend.ema_indicator(df["c"],200)
    df["atr"]=ta.volatility.average_true_range(df["h"],df["l"],df["c"],14)
    return df

# =========================
# 🧠 LOGICA
# =========================
def modo(df):
    if df["ema50"].iloc[-1] > df["ema200"].iloc[-1]:
        return "LONG"
    elif df["ema50"].iloc[-1] < df["ema200"].iloc[-1]:
        return "SHORT"
    return "NEUTRAL"

def condicion(df):
    v=df["atr"].iloc[-1]/df["c"].iloc[-1]
    if v<0.002:return "BAJA"
    elif v<0.006:return "NORMAL"
    return "ALTA"

def score(df):
    wr = winrate()
    base = 50

    if abs(df["ema50"].iloc[-1] - df["ema200"].iloc[-1]) > 0:
        base += 20 * wr

    if df["atr"].iloc[-1] > df["c"].mean() * 0.002:
        base += 15 * wr

    return base

# =========================
# ⚙️ PARAMETROS DINAMICOS
# =========================
def parametros(df, balance):
    p=df["c"].iloc[-1]
    atr=df["atr"].iloc[-1]

    if atr == 0:
        atr = p * 0.001

    m=modo(df)
    c=condicion(df)

    if c=="ALTA":
        return None

    riesgo = 0.01 * balance
    size = max(1, int(riesgo / atr))

    tp = p + atr*2 if m=="LONG" else p - atr*2
    sl = p - atr*1.5 if m=="LONG" else p + atr*1.5

    levels=5
    step=(atr*3)/levels

    return m,tp,sl,levels,step,size

# =========================
# 🚀 TRADING
# =========================
def order(pair,side,size):
    body={
        "instId":pair,
        "tdMode":"cross",
        "side":"buy" if side=="LONG" else "sell",
        "ordType":"market",
        "sz":str(size)
    }
    requests.post(BASE_URL+"/api/v5/trade/order",json=body,headers=headers("POST","/api/v5/trade/order",str(body)))

def grid(pair,price,levels,step,side,size):
    for i in range(1,levels+1):
        px=price-step*i if side=="LONG" else price+step*i
        body={
            "instId":pair,
            "tdMode":"cross",
            "side":"buy" if side=="LONG" else "sell",
            "ordType":"limit",
            "px":str(round(px,4)),
            "sz":str(size)
        }
        requests.post(BASE_URL+"/api/v5/trade/order",json=body,headers=headers("POST","/api/v5/trade/order",str(body)))

def tpsl(pair,tp,sl,side,size):
    body={
        "instId":pair,
        "tdMode":"cross",
        "side":"sell" if side=="LONG" else "buy",
        "ordType":"conditional",
        "tpTriggerPx":str(tp),
        "tpOrdPx":str(tp),
        "slTriggerPx":str(sl),
        "slOrdPx":str(sl),
        "sz":str(size)
    }
    requests.post(BASE_URL+"/api/v5/trade/order-algo",json=body,headers=headers("POST","/api/v5/trade/order-algo",str(body)))

def open_positions():
    path="/api/v5/account/positions"
    r=requests.get(BASE_URL+path,headers=headers("GET",path)).json()
    return len(r.get("data",[]))

# =========================
# 🔍 TOP PARES
# =========================
def best_pairs():
    candidatos=[]
    for p in get_pairs():
        try:
            df=get_candles(p)
            s=score(df)
            if s>60:
                candidatos.append((p,df,s))
        except:
            continue

    candidatos=sorted(candidatos,key=lambda x:x[2],reverse=True)
    return candidatos[:MAX_TRADES]

# =========================
# 🔁 LOOP PRINCIPAL
# =========================
def run():
    while True:
        try:
            balance=get_balance()
            abiertos=open_positions()

            if abiertos >= MAX_TRADES:
                print("⚠️ Máximo trades activos")
                time.sleep(120)
                continue

            pares=best_pairs()

            for p,df,s in pares:
                if open_positions() >= MAX_TRADES:
                    break

                params = parametros(df, balance)
                if not params:
                    continue

                m,tp,sl,levels,step,size=params
                price=df["c"].iloc[-1]

                print(f"🚀 {p} | {m} | size:{size} | balance:{balance}")

                order(p,m,size)
                grid(p,price,levels,step,m,size)
                tpsl(p,tp,sl,m,size)

            time.sleep(300)

        except Exception as e:
            print("ERROR:",e)
            traceback.print_exc()
            time.sleep(60)

if __name__=="__main__":
    run()