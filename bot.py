import time, hmac, base64, hashlib, requests, pandas as pd, ta, os, json
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

API_KEY = os.getenv("db75d70b-f577-40e5-b06c-60b9")
SECRET = os.getenv("db75d70b-f577-40e5-b06c-60b9")
PASSPHRASE = os.getenv("WXcv8089@")

BASE_URL = "https://www.okx.com"
CAPITAL = 50
AI_FILE = "ai_data.json"

# =========================
# 🧠 IA STORAGE
# =========================
def load_ai():
    if not os.path.exists(AI_FILE):
        return {"wins":0,"losses":0,"w_tendencia":40,"w_vol":30,"w_dd":30}
    return json.load(open(AI_FILE))

def save_ai(data):
    with open(AI_FILE,"w") as f:
        json.dump(data,f)

def update_ai(win):
    data = load_ai()
    if win: data["wins"] += 1
    else: data["losses"] += 1

    total = data["wins"] + data["losses"]
    if total > 5:
        winrate = data["wins"] / total

        # Ajuste simple adaptativo
        if winrate > 0.6:
            data["w_tendencia"] += 2
        else:
            data["w_vol"] += 2

    save_ai(data)

# =========================
# 🔐 AUTH
# =========================
def sign(msg):
    return base64.b64encode(hmac.new(SECRET.encode(), msg.encode(), hashlib.sha256).digest()).decode()

def headers(method, path, body=""):
    ts = datetime.utcnow().isoformat()+"Z"
    msg = ts+method+path+body
    return {
        "OK-ACCESS-KEY":API_KEY,
        "OK-ACCESS-SIGN":sign(msg),
        "OK-ACCESS-TIMESTAMP":ts,
        "OK-ACCESS-PASSPHRASE":PASSPHRASE,
        "Content-Type":"application/json"
    }

# =========================
# 📊 DATA
# =========================
def pairs():
    r = requests.get(BASE_URL+"/api/v5/market/tickers?instType=SWAP").json()
    return [x["instId"] for x in r["data"] if "USDT" in x["instId"]]

def candles(pair):
    r = requests.get(BASE_URL+f"/api/v5/market/candles?instId={pair}&bar=1H&limit=100").json()["data"]
    df = pd.DataFrame(r,columns=["t","o","h","l","c","v","","",""])
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
    e50,e200,p=df["ema50"].iloc[-1],df["ema200"].iloc[-1],df["c"].iloc[-1]
    if e50>e200: return "LONG"
    if e50<e200: return "SHORT"
    return "NEUTRAL"

def condicion(df):
    v=df["atr"].iloc[-1]/df["c"].iloc[-1]
    if v<0.002:return "BAJA"
    elif v<0.006:return "NORMAL"
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
def params(df):
    p=df["c"].iloc[-1]
    atr=df["atr"].iloc[-1]
    m=modo(df)
    c=condicion(df)

    if c=="BAJA": tp_f,sl_f,lev=1.2,1.0,5
    elif c=="NORMAL": tp_f,sl_f,lev=1.8,1.5,3
    else: tp_f,sl_f,lev=2.5,2.0,2

    tp=p+atr*tp_f if m=="LONG" else p-atr*tp_f
    sl=p-atr*sl_f if m=="LONG" else p+atr*sl_f

    grid_range=atr*3
    levels=8
    step=grid_range/levels

    size=max(1,int((0.02*CAPITAL)/atr))

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
        requests.post(BASE_URL+"/api/v5