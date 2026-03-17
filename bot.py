import time, hmac, base64, hashlib, requests, pandas as pd, ta, os, json, traceback
from dotenv import load_dotenv
from datetime import datetime

requests.packages.urllib3.disable_warnings()

load_dotenv()

API_KEY = os.getenv("db75d70b-f577-40e5-b06c-60b9c87584a7")
SECRET = os.getenv("DD0B0C2024162F50F4267C1D59C4AC81")
PASSPHRASE = os.getenv("WXcv8089@")

BASE_URL = "https://www.okx.com"
AI_FILE = "ai_trades.json"
MAX_TRADES = 3

# =========================
# 🧠 IA SEGURA
# =========================
def load_ai():
    try:
        if not os.path.exists(AI_FILE):
            return {"trades":[]}

        with open(AI_FILE, "r") as f:
            content = f.read().strip()

            if not content:
                return {"trades":[]}

            return json.loads(content)

    except Exception as e:
        print("Error IA:", e)
        return {"trades":[]}

def save_ai(data):
    try:
        with open(AI_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print("Error guardando IA:", e)

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
# 💰 BALANCE
# =========================
def get_balance():
    try:
        path="/api/v5/account/balance"
        r=requests.get(BASE_URL+path,headers=headers("GET",path)).json()

        if "data" not in r:
            return 50

        for d in r["data"][0]["details"]:
            if d["ccy"]=="USDT":
                return float(d["availBal"])

    except Exception as e:
        print("Error balance:", e)

    return 50

# =========================
# 📊 DATOS
# =========================
def get_pairs():
    try:
        data=requests.get(BASE_URL+"/api/v5/market/tickers?instType=SWAP").json().get("data",[])
        pairs=[]

        for x in data:
            try:
                if "USDT" not in x["instId"]:
                    continue

                vol=float(x.get("volCcy24h",0))

                if vol < 1000000:
                    continue

                pairs.append(x["instId"])
            except:
                continue

        return pairs

    except Exception as e:
        print("Error pairs:", e)
        return []

def get_candles(pair):
    try:
        data=requests.get(BASE_URL+f"/api/v5/market/candles?instId={pair}&bar=1H&limit=100").json().get("data",[])

        if not data:
            return None

        df=pd.DataFrame(data,columns=["t","o","h","l","c","v","","",""])

        df["c"]=df["c"].astype(float)
        df["h"]=df["h"].astype(float)
        df["l"]=df["l"].astype(float)

        df["ema50"]=ta.trend.ema_indicator(df["c"],50)
        df["ema200"]=ta.trend.ema_indicator(df["c"],200)
        df["atr"]=ta.volatility.average_true_range(df["h"],df["l"],df["c"],14)

        return df

    except Exception as e:
        print("Error candles:", pair, e)
        return None

# =========================
# 🧠 LOGICA
# =========================
def modo(df):
    e50=df["ema50"].iloc[-1]
    e200=df["ema200"].iloc[-1]

    if e50>e200:
        return "LONG"
    elif e50<e200:
        return "SHORT"
    return "NEUTRAL"

def condicion(df):
    try:
        precio=df["c"].iloc[-1]

        if precio == 0:
            return "NORMAL"

        atr=df["atr"].iloc[-1]
        v=atr/precio

        if v<0.002: return "BAJA"
        elif v<0.006: return "NORMAL"
        return "ALTA"

    except:
        return "NORMAL"

def score(df):
    try:
        wr=winrate()
        base=50

        if abs(df["ema50"].iloc[-1]-df["ema200"].iloc[-1])>0:
            base+=20*wr

        if df["atr"].iloc[-1]>df["c"].mean()*0.002:
            base+=15*wr

        return base

    except:
        return 0

# =========================
# ⚙️ PARAMETROS
# =========================
def parametros(df,balance):
    try:
        p=df["c"].iloc[-1]
        atr=df["atr"].iloc[-1]

        if atr==0:
            atr=p*0.001

        m=modo(df)
        c=condicion(df)

        if c=="ALTA":
            return None

        riesgo=0.01*balance
        size=max(1,int(riesgo/atr))

        if m=="LONG":
            tp=p+atr*2
            sl=p-atr*1.5
        elif m=="SHORT":
            tp=p-atr*2
            sl=p+atr*1.5
        else:
            tp=p+atr
            sl=p-atr

        levels=5
        step=(atr*3)/levels

        return m,tp,sl,levels,step,size

    except Exception as e:
        print("Error params:", e)
        return None

# =========================
# 🚀 TRADING
# =========================
def order(pair,side,size):
    try:
        body={
            "instId":pair,
            "tdMode":"cross",
            "side":"buy" if side=="LONG" else "sell",
            "ordType":"market",
            "sz":str(size)
        }

        requests.post(BASE_URL+"/api/v5/trade/order",
                      json=body,
                      headers=headers("POST","/api/v5/trade/order",str(body)))

    except Exception as e:
        print("Error order:", e)

def grid(pair,price,levels,step,side,size):
    try:
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

            requests.post(BASE_URL+"/api/v5/trade/order",
                          json=body,
                          headers=headers("POST","/api/v5/trade/order",str(body)))

    except Exception as e:
        print("Error grid:", e)

def tpsl(pair,tp,sl,side,size):
    try:
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

        requests.post(BASE_URL+"/api/v5/trade/order-algo",
                      json=body,
                      headers=headers("POST","/api/v5/trade/order-algo",str(body)))

    except Exception as e:
        print("Error tpsl:", e)

def open_positions():
    try:
        path="/api/v5/account/positions"
        r=requests.get(BASE_URL+path,headers=headers("GET",path)).json()

        if "data" not in r:
            return 0

        return len(r["data"])

    except Exception as e:
        print("Error posiciones:", e)
        return 0

# =========================
# 🔍 SELECCION
# =========================
def best_pairs():
    candidatos=[]

    for p in get_pairs():
        df=get_candles(p)
        if df is None:
            continue

        s=score(df)

        if s>60:
            candidatos.append((p,df,s))

    if not candidatos:
        return []

    candidatos=sorted(candidatos,key=lambda x:x[2],reverse=True)
    return candidatos[:MAX_TRADES]

# =========================
# 🔁 LOOP
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

            if not pares:
                print("❌ Sin oportunidades")
                time.sleep(300)
                continue

            for p,df,s in pares:
                if open_positions() >= MAX_TRADES:
                    break

                params=parametros(df,balance)

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
            print("ERROR GENERAL:",e)
            traceback.print_exc()
            time.sleep(60)

if __name__=="__main__":
    run()