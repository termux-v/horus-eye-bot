import os
import asyncio
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import httpx
import yfinance as yf
import pandas as pd
import numpy as np
import feedparser
import time
import gc
from datetime import time as dt_time, datetime
import pytz
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ==========================================
# ⚙️ SECURE CONFIGURATION (Environment Variables)
# ==========================================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
YOUR_CHAT_ID = os.getenv("YOUR_CHAT_ID")

IST = pytz.timezone('Asia/Kolkata')
DIVIDER = "━━━━━━━━━━━━━━━━━━━━━━━━"

# ==========================================
# 🌐 HEALTH CHECK SERVER (Render Sleep Fix)
# ==========================================
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"The Horus Eye Bot is Live 24/7 Utility Edition!")
    def log_message(self, format, *args):
        pass

def start_health_server():
    port = int(os.getenv("PORT", 8000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    print(f"✅ Health server running on port {port}")
    server.serve_forever()

# ==========================================
# 🌐 DYNAMIC STOCK UNIVERSE (Nifty 500 + Backup)
# ==========================================
async def get_dynamic_universe():
    try:
        url = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
        headers = {'User-Agent': 'Mozilla/5.0'}
        async with httpx.AsyncClient() as client:
            res = await client.get(url, headers=headers, timeout=10.0)
            if res.status_code == 200:
                lines = res.text.split('\n')
                symbols = [line.split(',')[2].strip() + ".NS" for line in lines[1:] if len(line.split(',')) > 2 and line.strip()]
                if len(symbols) > 100:
                    return symbols
    except Exception:
        pass
    
    # Robust Backup List (Top Liquid Stocks)
    return ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS", "SBIN.NS", "BHARTIARTL.NS", "ITC.NS", "LT.NS", "KOTAKBANK.NS", "AXISBANK.NS", "MARUTI.NS", "TATAMOTORS.NS", "M&M.NS", "TITAN.NS", "BAJFINANCE.NS", "HINDUNILVR.NS", "SUNPHARMA.NS", "ASIANPAINT.NS", "WIPRO.NS", "HCLTECH.NS", "TECHM.NS", "NESTLEIND.NS", "POWERGRID.NS", "NTPC.NS", "ONGC.NS", "COALINDIA.NS", "ADANIENT.NS", "JSWSTEEL.NS", "TATASTEEL.NS", "HINDALCO.NS", "ULTRACEMCO.NS", "GRASIM.NS", "ADANIPORTS.NS", "BPCL.NS", "EICHERMOT.NS", "HEROMOTOCO.NS", "ZOMATO.NS", "PAYTM.NS", "IRCTC.NS", "HAL.NS", "BEL.NS", "DIXON.NS", "POLYCAB.NS", "TRENT.NS", "TATAPOWER.NS", "DLF.NS", "GODREJPROP.NS", "PERSISTENT.NS", "COFORGE.NS", "CUMMINSIND.NS", "ABB.NS", "SIEMENS.NS", "BHEL.NS", "SAIL.NS", "NMDC.NS", "VEDL.NS", "GAIL.NS", "IOC.NS", "PFC.NS", "RECLTD.NS", "IRFC.NS", "ADANIGREEN.NS", "ADANIPOWER.NS", "LUPIN.NS", "AUROPHARMA.NS", "BIOCON.NS", "ALKEM.NS", "TORNTPHARM.NS", "SUZLON.NS"]

# ==========================================
# 🧠 DUAL AI ENGINE (Groq -> Gemini -> Fallback)
# ==========================================
async def get_deep_logic(symbol, news_text, tech_reason, fund_data):
    prompt = f"""Stock: {symbol}. Tech: {tech_reason}. News: {news_text}. Fundamentals: {fund_data}. 
    As an FII/Pro Trader, in 2 lines, explain WHY it's going up today and WHY it will go up TOMORROW. Mention FIIs, Govt, or Earnings. Keep it factual."""
    
    # 1. Primary: Groq API
    if GROQ_API_KEY and len(GROQ_API_KEY) > 10:
        for _ in range(2):
            try:
                async with httpx.AsyncClient() as client:
                    res = await client.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                        json={"model": "llama-3.1-8b-instant", "messages": [{"role": "user", "content": prompt}]},
                        timeout=10.0
                    )
                    if res.status_code == 200:
                        return res.json()["choices"][0]["message"]["content"].strip()
            except Exception:
                await asyncio.sleep(1)
            
    # 2. Backup: Gemini API
    if GEMINI_API_KEY and len(GEMINI_API_KEY) > 10:
        try:
            async with httpx.AsyncClient() as client:
                res = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}",
                    json={"contents": [{"parts": [{"text": prompt}]}]},
                    timeout=10.0
                )
                if res.status_code == 200:
                    return res.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception:
            pass
        
    return "Institutional volume breakout with strong price action. Expect continuation momentum tomorrow."

def get_news(symbol):
    try:
        url = f"https://news.google.com/rss/search?q={symbol.replace('.NS','')}+NSE+stock&hl=en-IN&gl=IN&ceid=IN:en"
        feed = feedparser.parse(url)
        return " | ".join([e.title for e in feed.entries[:2]]) if feed.entries else "No major news."
    except Exception:
        return "No major news."

# ==========================================
# 🕯️ CORE QUANT LOGIC (SMC + Price Action)
# ==========================================
def analyze_setup(df, nifty_close):
    if df is None or len(df) < 50: return None
    def sf(val): return float(val.iloc[0]) if isinstance(val, pd.Series) else float(val)
    try:
        df = df.copy()
        close = df['Close']
        ltp = sf(close.iloc[-1])
        prev_close = sf(close.iloc[-2])
        if prev_close == 0: return None
        chg = round(((ltp - prev_close) / prev_close) * 100, 2)
        
        # RSI & VWAP Calculation
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        loss_last = sf(loss.iloc[-1])
        rsi = 100.0 if loss_last == 0 else sf(100 - (100 / (1 + (sf(gain.iloc[-1]) / loss_last))))
        
        tp = (df['High'] + df['Low'] + df['Close']) / 3
        vol_sum = sf(df['Volume'].rolling(20).sum().iloc[-1])
        if vol_sum == 0: return None
        vwap = sf((tp * df['Volume']).rolling(20).sum().iloc[-1]) / vol_sum
        
        # Pivots
        high, low = sf(df['High'].iloc[-1]), sf(df['Low'].iloc[-1])
        pivot = (high + low + ltp) / 3
        r1 = (pivot * 2) - low
        s1 = (pivot * 2) - high

        # SMC Order Block
        df['Body'] = abs(df['Close'] - df['Open'])
        ob = df.tail(15).sort_values(by='Body', ascending=False).iloc[0]
        ob_low = sf(min(ob['Open'], ob['Close']))
        
        # Price Action Candles
        c2, c3 = df.iloc[-2], df.iloc[-1]
        def parts(c):
            body = abs(sf(c['Close']) - sf(c['Open']))
            up = sf(c['High']) - max(sf(c['Close']), sf(c['Open']))
            low = min(sf(c['Close']), sf(c['Open'])) - sf(c['Low'])
            return body, up, low, sf(c['Close']) > sf(c['Open'])
        b3, u3, l3, g3 = parts(c3)
        is_bullish_candle = (g3 and sf(c3['Close']) > sf(c2['Close'])) or (l3 > (2 * b3) and u3 < b3)
        
        vol_spike = sf(df['Volume'].iloc[-1]) > sf(df['Volume'].rolling(20).mean().iloc[-1]) * 1.5
        
        score = 0; reasons = []
        if 40 < rsi < 70: score += 2; reasons.append("RSI Bullish")
        elif rsi <= 40: score += 3; reasons.append("RSI Reversal")
        if ltp > vwap: score += 2; reasons.append("Above VWAP")
        if ltp > pivot: score += 1; reasons.append("Above Pivot")
        if vol_spike: score += 2; reasons.append("Vol Spike")
        if sf(ob['Close']) > sf(ob['Open']): score += 1; reasons.append("Demand OB")
        if is_bullish_candle: score += 2; reasons.append("Bullish Candle")

        # ATR Targets
        df['TR'] = np.maximum(df['High'] - df['Low'], np.maximum(abs(df['High'] - df['Close'].shift()), abs(df['Low'] - df['Close'].shift())))
        atr = sf(df['TR'].rolling(14).mean().iloc[-1])
        
        if score >= 6:
            entry = round(ltp, 1)
            sl = round(min(ob_low, s1) - (0.2 * atr), 1)
            t1 = round(entry + (1.5 * atr), 1)
            t2 = round(entry + (3.0 * atr), 1)
        else:
            return None

        tag = "🔴 PENNY" if ltp < 50 else "🟡 SMALL" if ltp < 500 else "🟢 MID" if ltp < 2000 else "💎 LARGE"
        
        return {"ltp": ltp, "chg": chg, "tag": tag, "score": score, "reasons": ", ".join(reasons), "entry": entry, "sl": sl, "t1": t1, "t2": t2, "r1": round(r1, 1)}
    except Exception:
        return None

# ==========================================
# 📅 REPORT GENERATOR
# ==========================================
async def generate_full_report(is_tomorrow=False):
    start_time = time.time()
    symbols = await get_dynamic_universe()
    
    nifty = await asyncio.to_thread(yf.download, "^NSEI", period="3mo", progress=False)
    if nifty.empty:
        return "❌ Data fetch failed. Market servers might be busy."

    all_bulls = []
    for i in range(0, len(symbols), 50):
        batch = symbols[i:i+50]
        try:
            data = await asyncio.to_thread(yf.download, batch, period="3mo", group_by="ticker", threads=True, progress=False)
            if data is not None and not data.empty:
                level0 = data.columns.get_level_values(0)
                for sym in batch:
                    if sym in level0:
                        res = analyze_setup(data[sym].dropna(), nifty)
                        if res:
                            res["symbol"] = sym.replace(".NS", "")
                            all_bulls.append(res)
        except Exception:
            pass
        await asyncio.sleep(0.5)
    
    gc.collect()

    if not all_bulls:
        return "⚠️ <b>No A+ Bullish setups found right now. Market is consolidating. Stay cautious.</b>"

    all_bulls.sort(key=lambda x: x["score"], reverse=True)
    top_5 = all_bulls[:5]
    others = all_bulls[5:20]
    duration = round(time.time() - start_time, 1)

    header = "TOMORROW'S MASTER PLAN" if is_tomorrow else "TODAY'S LIVE SETUPS"
    
    report = f"<b>👁️ THE HORUS EYE - {header}</b>\n"
    report += f"<i>{datetime.now(IST).strftime('%d %b %Y | %I:%M %p')} IST</i> | ⏱️ <i>Scan Time: {duration}s</i>\n"
    report += f"<i>Scanned: {len(symbols)} Stocks | Found: {len(all_bulls)} Bullish</i>\n"
    report += f"{DIVIDER}\n\n"
    report += f"<b>🔥 TOP 5 HIGH-CONVICTION TRADES</b>\n\n"
    
    for s in top_5:
        news = get_news(s['symbol'])
        fund = "N/A"
        try:
            info = await asyncio.to_thread(lambda: yf.Ticker(f"{s['symbol']}.NS").info)
            fund = f"PE: {info.get('trailingPE', 'N/A')}, Cap: {round(info.get('marketCap', 0)/10000000, 1)}Cr"
        except Exception:
            pass

        logic = await get_deep_logic(s['symbol'], news, s['reasons'], fund)
        report += f"{s['tag']} <b>{s['symbol']}</b> | <code>₹{s['ltp']}</code> (<code>+{s['chg']}%</code>)\n"
        report += f"🧠 <b>Logic:</b> <i>{logic}</i>\n"
        report += f"🟢 <b>Entry:</b> <code>₹{s['entry']}</code> | 🎯 <b>T1:</b> <code>₹{s['t1']}</code> | 🛑 <b>SL:</b> <code>₹{s['sl']}</code>\n\n"

    if others:
        report += f"{DIVIDER}\n<b>🚀 OTHER BULLISH STOCKS ({len(others)})</b>\n"
        for s in others:
            report += f"• <b>{s['symbol']}</b>: <code>₹{s['ltp']}</code> (+{s['chg']}%) | R1: <code>₹{s['r1']}</code>\n"

    return report

# ==========================================
# 🚀 TELEGRAM COMMANDS & AUTO-PILOT
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_html(
        f"<b>👁️ THE HORUS EYE - TRADER UTILITY BOT</b>\n{DIVIDER}\n"
        f"Pure Nifty 500 SMC & AI scanner for high-conviction trades.\n\n"
        f"<b>Commands:</b>\n🔹 /today - Scan Market for Today\n🔹 /tomorrow - Plan for Tomorrow\n\n"
        f"<i>Auto-reports active at 9:45 AM & 4:00 PM IST.</i>"
    )

async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_html("<i>⏳ Scanning Nifty 500 for Today's Bullish Setups... Please wait 1-2 mins.</i>")
    report = await generate_full_report(is_tomorrow=False)
    if len(report) > 4000:
        chunks = [report[i:i+4000] for i in range(0, len(report), 4000)]
        await msg.edit_text(chunks[0], parse_mode='HTML')
        for chunk in chunks[1:]: await update.message.reply_html(chunk)
    else: await msg.edit_text(report, parse_mode='HTML')

async def tomorrow_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_html("<i>⏳ Analyzing Data for Tomorrow's Master Plan... Please wait 1-2 mins.</i>")
    report = await generate_full_report(is_tomorrow=True)
    if len(report) > 4000:
        chunks = [report[i:i+4000] for i in range(0, len(report), 4000)]
        await msg.edit_text(chunks[0], parse_mode='HTML')
        for chunk in chunks[1:]: await update.message.reply_html(chunk)
    else: await msg.edit_text(report, parse_mode='HTML')

async def auto_morning(context: ContextTypes.DEFAULT_TYPE):
    if datetime.now(IST).weekday() > 4: return
    try:
        report = await generate_full_report(is_tomorrow=False)
        await context.bot.send_message(chat_id=YOUR_CHAT_ID, text="🌅 <b>TODAY'S PLAN</b>\n\n" + report, parse_mode='HTML')
    except Exception: pass

async def auto_evening(context: ContextTypes.DEFAULT_TYPE):
    if datetime.now(IST).weekday() > 4: return
    try:
        report = await generate_full_report(is_tomorrow=True)
        await context.bot.send_message(chat_id=YOUR_CHAT_ID, text="🌇 <b>TOMORROW'S MASTER PLAN</b>\n\n" + report, parse_mode='HTML')
    except Exception: pass

# ==========================================
# 🔄 MAIN LOOP (Self-Healing & Startup Ping)
# ==========================================
async def post_init(application):
    try:
        await application.bot.send_message(
            chat_id=YOUR_CHAT_ID,
            text="👁️ <b>The Horus Eye Bot is online and ready!</b>\n<i>Utility mode active.</i>",
            parse_mode='HTML'
        )
    except Exception:
        pass

if __name__ == '__main__':
    # Start Health Check background server for Render
    threading.Thread(target=start_health_server, daemon=True).start()
    
    while True:
        try:
            app = ApplicationBuilder().token(TELEGRAM_TOKEN).post_init(post_init).build()
            app.add_handler(CommandHandler("start", start))
            app.add_handler(CommandHandler("today", today_command))
            app.add_handler(CommandHandler("tomorrow", tomorrow_command))
            
            jq = app.job_queue
            if jq:
                jq.run_daily(auto_morning, time=dt_time(hour=9, minute=45, tzinfo=IST))
                jq.run_daily(auto_evening, time=dt_time(hour=16, minute=0, tzinfo=IST))
                
            print("👁️ Utility Horus Eye Bot is Live & Fully Operational...")
            app.run_polling(drop_pending_updates=True)
        except Exception as e:
            print(f"⚠️ Self-healing recovery triggered: {e}")
            time.sleep(10)
            continue
  
