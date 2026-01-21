# ============================================================
# RicoTradingBot 2026 — FULL INTEGRATED VERSION
# Login • Charts • Paper Trading • Binance Live Trading
# ============================================================

import streamlit as st
import pandas as pd
import ta
import sqlite3
import hashlib
from datetime import datetime, timedelta
from binance.client import Client

# ============================================================
# APP SETUP
# ============================================================
st.set_page_config(page_title="RicoTradingBot 2026", page_icon="📈", layout="wide")

st.markdown("""
<style>
.stApp { background:#0e1117; color:#e6edf3; }
h1,h2 { color:#58a6ff; }
.card { background:#161b22; padding:16px; border-radius:14px; }
</style>
""", unsafe_allow_html=True)

st.title("🚀 RicoTradingBot 2026")

# ============================================================
# DATABASE
# ============================================================
conn = sqlite3.connect("app.db", check_same_thread=False)
c = conn.cursor()
c.execute("""
CREATE TABLE IF NOT EXISTS users(
 email TEXT PRIMARY KEY,
 password TEXT,
 balance REAL,
 last_login TEXT
)
""")
conn.commit()

def hp(p): return hashlib.sha256(p.encode()).hexdigest()

# ============================================================
# LOGIN
# ============================================================
SESSION_TIMEOUT = 30

def expired():
    if "login_time" not in st.session_state:
        return True
    return datetime.now() - st.session_state.login_time > timedelta(minutes=SESSION_TIMEOUT)

if "user" not in st.session_state or expired():
    st.session_state.clear()
    st.subheader("🔐 Login / Registrierung")

    email = st.text_input("E-Mail")
    pw = st.text_input("Passwort", type="password")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Login"):
            u = c.execute(
                "SELECT * FROM users WHERE email=? AND password=?",
                (email, hp(pw))
            ).fetchone()
            if u:
                st.session_state.user = u
                st.session_state.login_time = datetime.now()
                c.execute("UPDATE users SET last_login=? WHERE email=?",
                          (datetime.now().isoformat(), email))
                conn.commit()
                st.rerun()
            else:
                st.error("Login fehlgeschlagen")

    with col2:
        if st.button("Registrieren"):
            try:
                c.execute(
                    "INSERT INTO users VALUES (?,?,?,?)",
                    (email, hp(pw), 1000.0, "")
                )
                conn.commit()
                st.success("Account erstellt – jetzt einloggen")
            except:
                st.error("User existiert bereits")

    st.stop()

email, _, balance, last_login = st.session_state.user

# ============================================================
# SIDEBAR SETTINGS
# ============================================================
st.sidebar.subheader("⚙️ Einstellungen")

BOT_ENABLED = st.sidebar.toggle("🤖 Bot aktivieren", False)
BOT_MODE = st.sidebar.radio("Modus", ["🧪 Paper Trading", "💰 Echtgeld"], 0)

API_KEY = st.sidebar.text_input("Binance API Key", type="password")
API_SECRET = st.sidebar.text_input("Binance API Secret", type="password")

ENABLE_LIVE = BOT_MODE == "💰 Echtgeld" and BOT_ENABLED and API_KEY and API_SECRET

# ============================================================
# BINANCE CLIENT
# ============================================================
client = Client(API_KEY, API_SECRET) if ENABLE_LIVE else Client()

# ============================================================
# BOT CONFIG
# ============================================================
SYMBOL = "BTCUSDT"
TRADE_SIZE = 0.001
EMA_FAST = 9
EMA_SLOW = 21
RSI_BUY = 40
RSI_SELL = 60
TP_PCT = 0.15
SL_PCT = 0.10
MAX_TRADES_DAY = 10

if "bot" not in st.session_state:
    st.session_state.bot = {
        "pos": None,
        "entry": 0.0,
        "trades": 0,
        "pnl": 0.0,
        "log": [],
        "day": datetime.now().date()
    }

# ============================================================
# MARKET DATA
# ============================================================
@st.cache_data(ttl=10)
def load_data():
    k = client.get_klines(symbol=SYMBOL,
                          interval=Client.KLINE_INTERVAL_1MINUTE,
                          limit=200)
    df = pd.DataFrame(k, columns=[
        "t","o","h","l","c","v","ct","q","n","tb","tq","i"
    ])
    df["t"] = pd.to_datetime(df["t"], unit="ms")
    df["c"] = df["c"].astype(float)
    df["ema_fast"] = ta.trend.EMAIndicator(df["c"], EMA_FAST).ema_indicator()
    df["ema_slow"] = ta.trend.EMAIndicator(df["c"], EMA_SLOW).ema_indicator()
    df["rsi"] = ta.momentum.RSIIndicator(df["c"]).rsi()
    return df

df = load_data()
price = df.iloc[-1]["c"]

# ============================================================
# BOT ENGINE
# ============================================================
bot = st.session_state.bot

if bot["day"] != datetime.now().date():
    bot.update({"trades":0,"pnl":0.0,"day":datetime.now().date()})

if BOT_ENABLED and bot["trades"] < MAX_TRADES_DAY:
    if bot["pos"] is None:
        if df.iloc[-1]["rsi"] < RSI_BUY and df.iloc[-1]["ema_fast"] > df.iloc[-1]["ema_slow"]:
            bot["pos"] = "LONG"
            bot["entry"] = price
            bot["trades"] += 1
            bot["log"].append(f"{datetime.now()} BUY @ {price:.2f}")
            if ENABLE_LIVE:
                client.create_order(symbol=SYMBOL, side="BUY",
                                    type="MARKET", quantity=TRADE_SIZE)

    else:
        tp = bot["entry"] * (1 + TP_PCT/100)
        sl = bot["entry"] * (1 - SL_PCT/100)
        if price >= tp or price <= sl or df.iloc[-1]["rsi"] > RSI_SELL:
            pnl = (price - bot["entry"]) * TRADE_SIZE
            bot["pnl"] += pnl
            bot["pos"] = None
            bot["log"].append(f"{datetime.now()} SELL @ {price:.2f} | PnL {pnl:.2f}")
            if ENABLE_LIVE:
                client.create_order(symbol=SYMBOL, side="SELL",
                                    type="MARKET", quantity=TRADE_SIZE)

# ============================================================
# UI
# ============================================================
page = st.sidebar.radio("Navigation", ["📊 Charts", "💼 Konto", "🤖 Bot"])

if page == "📊 Charts":
    st.subheader("📊 BTC Chart")
    st.line_chart(df.set_index("t")[["c","ema_fast","ema_slow"]])

elif page == "💼 Konto":
    st.subheader("💼 Konto")
    st.markdown(f"""
    <div class="card">
    <b>E-Mail:</b> {email}<br>
    <b>Guthaben:</b> {balance:.2f} USDT<br>
    <b>Letzter Login:</b> {last_login}
    </div>
    """, unsafe_allow_html=True)

elif page == "🤖 Bot":
    st.subheader("🤖 Bot Status")
    st.write("Position:", bot["pos"])
    st.write("Entry:", bot["entry"])
    st.write("Trades heute:", bot["trades"])
    st.write("Tages-PnL:", round(bot["pnl"], 2))
    st.markdown("**Letzte Trades:**")
    for l in bot["log"][-5:]:
        st.code(l)

st.caption("🌐 Ziel-URL: https://ricotradingbot2026.streamlit.app")
