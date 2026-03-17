import time, hmac, base64, hashlib, requests, pandas as pd, ta, os, json, traceback
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

API_KEY = os.getenv("db75d70b-f577-40e5-b06c-60b9c87584a7")
SECRET = os.getenv("DD0B0C2024162F50F4267C1D59C4AC81")
PASSPHRASE = os.getenv("WXcv8089@")

BASE_URL = "https://www.okx.com"
CAPITAL = 50
AI_FILE = "ai_data.json"

# =========================
# 🧠 IA STORAGE
# =========================
def load_ai():
    try:
        if not os.path.exists(AI_FILE):
            return {"wins":0,"losses":0,"w_tendencia":40,"w_vol":30,"w_dd":30}
        return json.load(open(AI_FILE))
    except:
        return {"wins":0,"losses":0,"w_tendencia":40,"w_vol":30,"w_dd":30}

def save_ai(data):
    try:
        with open(AI_FILE,"w") as f:
            json.dump(data,f,indent=2)
    except:
        pass

def update_ai(win):
    data=load_ai()
    if win: data["wins"]+=1
    else: data["losses"]+=1

    total=data["wins"]+data["losses"]

    if total>5:
        winrate=data["wins"]/total
        if winrate>0.6:
            data["w_tendencia"]+=1
        else:
            data["w_vol"]+=1

    save_ai(data)

# =========================
# 🔐 AUTH
# =========================
def sign(msg):
    return base64.b64encode(hmac.new(SECRET.encode(), msg.encode(), hashlib.sha256).digest()).decode()

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
# 📊 DATOS
# =========================
def get_pairs():
    url=BASE_URL+"/api/v5/market/tickers?instType=SWAP"
    data=requests.get(url).json()["data"]

    pairs=[]
    for x in data:
        try:
            inst=x["instId"]
            if "USDT" not in inst:
                continue

            vol=float(x.get("volCcy24h",0))
            last=float(x.get("last",0))

            if vol<1000000:
                continue

            if last<=0:
                continue

            pairs.append(inst)
        except:
            continue

    return pairs

def get_candles(pair):
    r=requests.get(BASE_URL+f"/api/v5/market/candles?instId={pair}&bar=1H&limit=100").json()["data"]
    df=pd.DataFrame(r,columns=["t","o","h","l","c","v","","",""])

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
    e50=df["ema50"].iloc[-1]
    e200=df["ema200"].iloc[-1]

    if e50>e200:
        return "LONG"
    elif e50<e200:
        return "SHORT"
    return "NEUTRAL"

def condicion(df):
    atr=df["atr"].iloc[-1]
    p=df["c"].iloc[-1]

    if p==0:
        return "NORMAL"

    v=atr/p

    if v<0.002:
        return "BAJA"
    elif v<0.006:
        return "NORMAL"
    return "ALTA"

def score(df):
    ai=load_ai()
    s=0

    if abs(df["ema50"].iloc[-1]-df["ema200"].iloc[-1])>0:
        s+=ai["w_tendencia"]

    if df["atr"].iloc[-1]>df["c"].mean()*0.002:
        s+=ai["w_vol"]

    if (df["c"].max()-df["c"].min())/df["c"].max()<0.2:
        s+=ai["w_dd"]

    return s

# =========================
# ⚙️ PARAMETROS
# =========================
def parametros(df):
    p=df["c"].iloc[-1]
    atr=df["atr"].iloc[-1]

    if atr==0:
        atr=p*0.001

    m=modo(df)
    c=condicion(df)

    if c=="BAJA":
        tp_f,sl_f,lev=1.2,1.0,5
    elif c=="NORMAL":
        tp_f,sl_f,lev=1.8,1.5,3
    else:
        tp_f,sl_f,lev=2.5,2.0,2

    if m=="LONG":
        tp=p+atr*tp_f
        sl=p-atr*sl_f
    elif m=="SHORT":
        tp=p-atr*tp_f
        sl=p+atr*sl_f
    else:
        tp=p+atr*(tp_f/2)
        sl=p-atr*(sl_f/2)

    grid_range=atr*3
    levels=5
    step=grid_range/levels

    riesgo=0.01*CAPITAL
    size=max(1,int(riesgo/atr))

    return m,tp,sl,lev,levels,step,size

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

def has_position(pair):
    r=requests.get(BASE_URL+f"/api/v5/account/positions?instId={pair}",
                   headers=headers("GET",f"/api/v5/account/positions?instId={pair}")).json()
    return len(r.get("data",[]))>0

# =========================
# 🔍 SELECCIÓN PRO
# =========================
def best_pair():
    candidatos=[]

    for p in get_pairs():
        try:
            df=get_candles(p)
            s=score(df)

            if s>70:
                candidatos.append((p,df,s))
        except:
            continue

    candidatos=sorted(candidatos,key=lambda x:x[2],reverse=True)
    top5=candidatos[:5]

    if not top5:
        return None,None

    return top5[0][0],top5[0][1]

# =========================
# 🔁 LOOP
# =========================
def run():
    while True:
        try:
            pair,df=best_pair()

            if pair:

                if condicion(df)=="ALTA":
                    print("⚠️ Mercado peligroso, evitando")
                    time.sleep(300)
                    continue

                if has_position(pair):
                    print("⚠️ Ya hay operación activa")
                    time.sleep(120)
                    update_ai(True)
                    continue

                m,tp,sl,lev,levels,step,size=parametros(df)
                price=df["c"].iloc[-1]

                print(f"""
🔥 BOT ACTIVO

Par: {pair}
Modo: {m}
Precio: {price}

TP: {tp}
SL: {sl}
Lev: {lev}
Size: {size}
""")

                order(pair,m,size)
                grid(pair,price,levels,step,m,size)
                tpsl(pair,tp,sl,m,size)

            else:
                print("❌ Sin oportunidades")

            time.sleep(300)

        except Exception as e:
            print("ERROR:",e)
            traceback.print_exc()
            time.sleep(60)

if __name__=="__main__":
    run()