import time, json, hmac, base64, requests
from datetime import datetime, UTC

# ========= CONFIG =========
API_KEY = "db75d70b-f577-40e5-b06c-60b9c87584a7"
SECRET_KEY = "DD0B0C2024162F50F4267C1D59C4AC81"
PASSPHRASE = "WXcv8089@"

BASE_URL = "https://www.okx.com"

SYMBOL = "BTC-USDT-SWAP"
RIESGO = 0.05
LEVERAGE = "5"

# ========= LOG =========
def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

# ========= AUTH =========
def sign(ts, method, path, body=""):
    msg = f"{ts}{method}{path}{body}"
    return base64.b64encode(
        hmac.new(SECRET_KEY.encode(), msg.encode(), digestmod="sha256").digest()
    ).decode()

def headers(method, path, body=""):
    ts = datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00","Z")
    return {
        "OK-ACCESS-KEY": API_KEY,
        "OK-ACCESS-SIGN": sign(ts, method, path, body),
        "OK-ACCESS-TIMESTAMP": ts,
        "OK-ACCESS-PASSPHRASE": PASSPHRASE,
        "Content-Type": "application/json"
    }

# ========= BALANCE =========
def get_balance():
    try:
        r = requests.get(
            BASE_URL+"/api/v5/account/balance",
            headers=headers("GET","/api/v5/account/balance")
        ).json()

        for d in r["data"][0]["details"]:
            if d["ccy"] == "USDT":
                return float(d["availEq"])
    except:
        return None

# ========= PRECIO =========
def get_price():
    r = requests.get(
        f"{BASE_URL}/api/v5/market/ticker?instId={SYMBOL}"
    ).json()

    return float(r["data"][0]["last"])

# ========= LEVERAGE =========
def set_leverage():
    body = json.dumps({
        "instId": SYMBOL,
        "lever": LEVERAGE,
        "mgnMode": "isolated"
    })

    r = requests.post(
        BASE_URL + "/api/v5/account/set-leverage",
        headers=headers("POST", "/api/v5/account/set-leverage", body),
        data=body
    ).json()

    log(f"⚙️ Leverage: {r}")

# ========= SIZE =========
def get_size(balance, price):
    size = (balance * RIESGO) / price

    lot = 0.001  # BTC
    size = max(size, lot)
    size = (size // lot) * lot

    return round(size, 6)

# ========= ORDEN =========
def place_order(side, balance):

    price = get_price()
    size = get_size(balance, price)

    body = json.dumps({
        "instId": SYMBOL,
        "tdMode": "isolated",
        "side": side,
        "posSide": "long" if side == "buy" else "short",
        "ordType": "market",
        "sz": str(size)
    })

    r = requests.post(
        BASE_URL+"/api/v5/trade/order",
        headers=headers("POST","/api/v5/trade/order",body),
        data=body
    ).json()

    log(f"📊 {r}")

# ========= BOT =========
def run():
    log("🚀 BOT SIMPLE OKX")

    set_leverage()

    while True:
        try:
            balance = get_balance()

            if not balance:
                log("❌ sin balance")
                time.sleep(10)
                continue

            log(f"💰 {balance} USDT")

            if balance < 5:
                log("⚠️ saldo bajo")
                time.sleep(60)
                continue

            # 🔥 TEST: compra cada ciclo
            place_order("buy", balance)

            time.sleep(60)

        except Exception as e:
            log(f"❌ {e}")
            time.sleep(10)

# ========= START =========
run()