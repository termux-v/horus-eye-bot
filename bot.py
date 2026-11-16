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
# ⚙️ CONFIGURATION
# ==========================================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "YOUR_TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "YOUR_GROQ_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "YOUR_GEMINI_KEY")
YOUR_CHAT_ID = os.getenv("YOUR_CHAT_ID", "YOUR_CHAT_ID")

IST = pytz.timezone('Asia/Kolkata')
DIVIDER = "━━━━━━━━━━━━━━━━━━━━━━━━"

# ==========================================
# 🌐 HEALTH CHECK SERVER
# ==========================================
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"The Horus Eye is Live!")
    def log_message(self, format, *args): pass

def start_health_server():
    port = int(os.getenv("PORT", 8000))
    HTTPServer(("0.0.0.0", port), HealthCheckHandler).serve_forever()

# ==========================================
# 📊 SECTOR SCANNER (Naya Feature)
# ==========================================
async def get_sector_performance():
    """यह देखता है कि आज कौन सा सेक्टर सबसे ज़्यादा मजबूत है"""
    sectors = {
        "IT": "^CNXIT", "BANK": "^NSEBANK", "AUTO": "^CNXAUTO", 
        "PHARMA": "^CNXPHARMA", "FMCG": "^CNXFMCG", "METAL": "^CNXMETAL"
    }
    perf = []
    for name, ticker in sectors.items():
        try:
            df = await asyncio.to_thread(yf.download, ticker, period="2d", progress=False)
            if not df.empty:
                chg = ((df['Close'].iloc[-1] - df['Close'].iloc[-2]) / df['Close'].iloc[-2]) * 100
                perf.append({"name": name, "chg": round(float(chg), 2)})
        except: pass
    
    perf.sort(key=lambda x: x["chg"], reverse=True)
    return perf

# ==========================================
# 📰 MULTI-SOURCE NEWS ENGINE (Naya Feature)
# ==========================================
def get_multi_news(symbol):
    clean_sym = symbol.replace('.NS', '')
    news = []
    
    # 1. Google News
    try:
        url1 = f"https://news.google.com/rss/search?q={clean_sym}+NSE+stock&hl=en-IN&gl=IN&ceid=IN:en"
        feed1 = feedparser.parse(url1)
        news.extend([e.title for e in feed1.entries[:2]])
    except: pass
    
    # 2. Economic Times Markets
    try:
        url2 = "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms"
        feed2 = feedparser.parse(url2)
        news.extend([e.title for e in feed2.entries[:2]])
    except: pass

    return " | ".join(news[:4]) if news else "No major news."

# ==========================================
# 🧠 DUAL AI ENGINE
# ==========================================
async def get_deep_logic(symbol, news_text, tech_reason, fund_data):
    prompt = f"""Stock: {symbol}. Tech: {tech_reason}. News: {news_text}. Fundamentals: {fund_data}. 
    As an FII/Pro Trader, in 2 lines, explain WHY it's going up today and WHY it will go up TOMORROW. Mention FIIs, Govt, or Earnings. Keep it factual."""
    
    if GROQ_API_KEY and len(GROQ_API_KEY) > 10:
        for _ in range(2):
            try:
                async with httpx.AsyncClient() as client:
                    res = await client.post("https://api.groq.com/openai/v1/chat/completions",
                        headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                        json={"model": "llama-3.1-8b-instant", "messages": [{"role": "user", "content": prompt}]}, timeout=12.0)
                    if res.status_code == 200: return res.json()["choices"][0]["message"]["content"].strip()
            except: await asyncio.sleep(1)
            
    if GEMINI_API_KEY and len(GEMINI_API_KEY) > 10:
        try:
            async with httpx.AsyncClient() as client:
                res = await client.post(f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}",
                    json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=12.0)
                if res.status_code == 200: return res.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        except: pass
    return "Institutional volume breakout with strong price action."

# ==========================================
# 🕯️ ADVANCED QUANT LOGIC (Pivots + SMC)
# ==========================================
def analyze_setup(df, sector_trend):
    if df is None or len(df) < 50: return None
    def sf(val): return float(val.iloc[0]) if isinstance(val, pd.Series) else float(val)
    try:
        df = df.copy()
        close = df['Close']
        ltp = sf(close.iloc[-1])
        prev_close = sf(close.iloc[-2])
        if prev_close == 0: return None
        chg = round(((ltp - prev_close) / prev_close) * 100, 2)
        
        # 1. RSI & VWAP
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        loss_last = sf(loss.iloc[-1])
        rsi = 100.0 if loss_last == 0 else sf(100 - (100 / (1 + (sf(gain.iloc[-1]) / loss_last))))
        
        tp = (df['High'] + df['Low'] + df['Close']) / 3
        vol_sum = sf(df['Volume'].rolling(20).sum().iloc[-1])
        if vol_sum == 0: return None
        vwap = sf((tp * df['Volume']).rolling(20).sum().iloc[-1]) / vol_sum
        
        # 2. Pivot Points (Support/Resistance)
        high, low = sf(df['High'].iloc[-1]), sf(df['Low'].iloc[-1])
        pivot = (high + low + ltp) / 3
        r1 = (pivot * 2) - low
        s1 = (pivot * 2) - high

        # 3. SMC (Order Block)
        df['Body'] = abs(df['Close'] - df['Open'])
        ob = df.tail(15).sort_values(by='Body', ascending=False).iloc[0]
        ob_low = sf(min(ob['Open'], ob['Close']))
        
        # 4. Scoring
        score = 0; reasons = []
        if 40 < rsi < 70: score += 2; reasons.append("RSI Bullish")
        elif rsi <= 40: score += 3; reasons.append("RSI Reversal")
        if ltp > vwap: score += 2; reasons.append("Above VWAP")
        if ltp > pivot: score += 1; reasons.append("Above Pivot")
        if sf(ob['Close']) > sf(ob['Open']): score += 1; reasons.append("Demand OB")
        
        # Sector Boost (अगर सेक्टर मजबूत है, तो स्कोर बढ़ाओ)
        if sector_trend > 0: score += 1; reasons.append("Strong Sector")

        # 5. Targets
        df['TR'] = np.maximum(df['High'] - df['Low'], np.maximum(abs(df['High'] - df['Close'].shift()), abs(df['Low'] - df['Close'].shift())))
        atr = sf(df['TR'].rolling(14).mean().iloc[-1])
        
        if score >= 6:
            entry = round(ltp, 1)
            sl = round(min(ob_low, s1) - (0.2 * atr), 1) # SL या तो OB के नीचे या S1 के नीचे
            t1 = round(entry + (1.5 * atr), 1)
            t2 = round(entry + (3.0 * atr), 1)
        else: return None

        tag = "🔴 PENNY" if ltp < 50 else "🟡 SMALL" if ltp < 500 else "🟢 MID" if ltp < 2000 else "💎 LARGE"
        
        return {"ltp": ltp, "chg": chg, "tag": tag, "score": score, "reasons": ", ".join(reasons), 
                "entry": entry, "sl": sl, "t1": t1, "t2": t2, "r1": round(r1, 1)}
    except: return None

# ==========================================
# 📅 REPORT GENERATOR
# ==========================================
async def generate_full_report(is_tomorrow=False):
    # 1. Sector Check
    sectors = await get_sector_performance()
    top_sector = sectors[0] if sectors else {"name": "NIFTY", "chg": 0}

    # 2. Get Universe (Nifty 500 from NSE)
    try:
        url = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
        async with httpx.AsyncClient() as client:
            res = await client.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10.0)
            symbols = [line.split(',')[2].strip() + ".NS" for line in res.text.split('\n')[1:] if len(line.split(',')) > 2]
            if len(symbols) < 100: raise Exception("NSE Blocked")
    except:
        # Fallback Top 100
        symbols = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS", "SBIN.NS", "BHARTIARTL.NS", "ITC.NS", "LT.NS", "KOTAKBANK.NS", "AXISBANK.NS", "MARUTI.NS", "TATAMOTORS.NS", "M&M.NS", "TITAN.NS"]

    all_bulls = []
    # 3. Batch Download & Analyze
    for i in range(0, len(symbols), 50):
        batch = symbols[i:i+50]
        try:
            data = await asyncio.to_thread(yf.download, batch, period="3mo", group_by="ticker", threads=True, progress=False)
            if data is not None and not data.empty:
                for sym in batch:
                    if sym in data.columns.get_level_values(0):
                        res = analyze_setup(data[sym].dropna(), top_sector['chg'])
                        if res: res["symbol"] = sym.replace(".NS", ""); all_bulls.append(res)
        except: pass
        await asyncio.sleep(1)
    
    gc.collect()

    if not all_bulls:
        return "⚠️ <b>No A+ Bullish setups found today. Market is choppy. Stay in cash.</b>"

    all_bulls.sort(key=lambda x: x["score"], reverse=True)
    top_3 = all_bulls[:3]
    others = all_bulls[3:15]

    header = "TOMORROW'S MASTER PLAN" if is_tomorrow else "TODAY'S LIVE SETUPS"
    
    report = f"<b>👁️ THE HORUS EYE - {header}</b>\n"
    report += f"<i>{datetime.now(IST).strftime('%d %b %Y | %I:%M %p')} IST</i>\n"
    report += f"🏆 <b>Top Sector:</b> {top_sector['name']} (<code>{top_sector['chg']}%</code>)\n"
    report += f"<i>Scanned: {len(symbols)} Stocks | Found: {len(all_bulls)} Bullish</i>\n"
    report += f"{DIVIDER}\n\n"
    report += f"<b>🔥 TOP 3 HIGH-CONVICTION TRADES</b>\n\n"
    
    for s in top_3:
        news = get_multi_news(s['symbol'])
        # Fundamental quick data
        fund = "N/A"
        try:
            info = await asyncio.to_thread(lambda: yf.Ticker(f"{s['symbol']}.NS").info)
            fund = f"PE: {info.get('trailingPE', 'N/A')}, Cap: {round(info.get('marketCap', 0)/10000000, 1)}Cr"
        except: pass

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
# 🚀 TELEGRAM COMMANDS
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_html(
        f"<b>👁️ THE HORUS EYE - MULTI-SOURCE ENGINE</b>\n{DIVIDER}\n"
        f"I scan Nifty 500, check Sector Strength, and use Multi-Source News for deep logic.\n\n"
        f"🔹 /today - Scan Market for Today\n🔹 /tomorrow - Plan for Tomorrow\n"
    )

async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_html("<i>⏳ Scanning Sectors & Nifty 500... Please wait 1-2 mins.</i>")
    report = await generate_full_report(is_tomorrow=False)
    if len(report) > 4000:
        chunks = [report[i:i+4000] for i in range(0, len(report), 4000)]
        await msg.edit_text(chunks[0], parse_mode='HTML')
        for chunk in chunks[1:]: await update.message.reply_html(chunk)
    else: await msg.edit_text(report, parse_mode='HTML')

async def tomorrow_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_html("<i>⏳ Analyzing Tomorrow's Master Plan...</i>")
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
    except: pass

async def auto_evening(context: ContextTypes.DEFAULT_TYPE):
    if datetime.now(IST).weekday() > 4: return
    try:
        report = await generate_full_report(is_tomorrow=True)
        await context.bot.send_message(chat_id=YOUR_CHAT_ID, text="🌇 <b>TOMORROW'S MASTER PLAN</b>\n\n" + report, parse_mode='HTML')
    except: pass

# ==========================================
# 🔄 MAIN LOOP
# ==========================================
if __name__ == '__main__':
    threading.Thread(target=start_health_server, daemon=True).start()
    while True:
        try:
            app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
            app.add_handler(CommandHandler("start", start))
            app.add_handler(CommandHandler("today", today_command))
            app.add_handler(CommandHandler("tomorrow", tomorrow_command))
            
            jq = app.job_queue
            if jq:
                jq.run_daily(auto_morning, time=dt_time(hour=9, minute=45, tzinfo=IST))
                jq.run_daily(auto_evening, time=dt_time(hour=16, minute=0, tzinfo=IST))
                
            app.run_polling(drop_pending_updates=True)
        except Exception as e:
            print(f"⚠️ Self-healing: {e}")
            time.sleep(10)
            continue
