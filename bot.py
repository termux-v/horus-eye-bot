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
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# ==========================================
# ⚙️ CONFIGURATION
# ==========================================
TELEGRAM_TOKEN = "9057274095:AAFUICR6sV4j60bViAheeKn7MLYzSkxpr70".strip()
YOUR_CHAT_ID = "6082045625".strip()

IST = pytz.timezone('Asia/Kolkata')
DIVIDER = "━━━━━━━━━━━━━━━━━━━━━━━━"

# ==========================================
# 🛑 CUSTOM API SLOT (यहाँ अपनी APIs जोड़ें)
# ==========================================
async def fetch_custom_data(symbol):
    """
    यहाँ आप अपनी खुद की APIs जोड़ सकते हैं (जैसे FII/DII, ऑप्शन चेन)। 
    अभी के लिए यह खाली है, लेकिन आप इसे यहाँ जोड़ सकते हैं।
    """
    custom_info = ""
    try:
        # उदाहरण: 
        # async with httpx.AsyncClient() as client:
        #     res = await client.get(f"https://api.example.com/data?symbol={symbol}")
        #     custom_info = res.json().get("summary", "")
        pass 
    except Exception:
        pass
    return custom_info

# ==========================================
# 🌐 HEALTH CHECK SERVER (Render Sleep Fix)
# ==========================================
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"The Horus Eye Bot is Fully Operational 24/7!")
    def log_message(self, format, *args): pass

def start_health_server():
    port = int(os.getenv("PORT", 8000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

# ==========================================
# 🌐 DYNAMIC STOCK UNIVERSE (Nifty 500)
# ==========================================
async def get_dynamic_universe():
    try:
        url = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        async with httpx.AsyncClient() as client:
            res = await client.get(url, headers=headers, timeout=10.0)
            if res.status_code == 200:
                lines = res.text.split('\n')
                symbols = [line.split(',')[2].strip() + ".NS" for line in lines[1:] if len(line.split(',')) > 2 and line.strip()]
                if len(symbols) > 100: return symbols
    except Exception: pass
    
    # Fallback Top 100 Liquid Stocks
    return ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS", "SBIN.NS", "BHARTIARTL.NS", "ITC.NS", "LT.NS", "KOTAKBANK.NS", "AXISBANK.NS", "MARUTI.NS", "TATAMOTORS.NS", "M&M.NS", "TITAN.NS", "BAJFINANCE.NS", "HINDUNILVR.NS", "SUNPHARMA.NS", "ASIANPAINT.NS", "WIPRO.NS", "HCLTECH.NS", "TECHM.NS", "NESTLEIND.NS", "POWERGRID.NS", "NTPC.NS", "ONGC.NS", "COALINDIA.NS", "ADANIENT.NS", "JSWSTEEL.NS", "TATASTEEL.NS", "HINDALCO.NS", "ULTRACEMCO.NS", "GRASIM.NS", "ADANIPORTS.NS", "BPCL.NS", "EICHERMOT.NS", "HEROMOTOCO.NS", "ZOMATO.NS", "PAYTM.NS", "IRCTC.NS", "HAL.NS", "BEL.NS", "DIXON.NS", "POLYCAB.NS", "TRENT.NS", "TATAPOWER.NS", "DLF.NS", "GODREJPROP.NS", "PERSISTENT.NS", "COFORGE.NS", "CUMMINSIND.NS", "ABB.NS", "SIEMENS.NS", "BHEL.NS", "SAIL.NS", "NMDC.NS", "VEDL.NS", "GAIL.NS", "IOC.NS", "PFC.NS", "RECLTD.NS", "IRFC.NS", "ADANIGREEN.NS", "ADANIPOWER.NS", "LUPIN.NS", "AUROPHARMA.NS", "BIOCON.NS", "ALKEM.NS", "TORNTPHARM.NS", "SUZLON.NS"]

# ==========================================
# 📰 NEWS ENGINE
# ==========================================
def get_news(symbol):
    try:
        url = f"https://news.google.com/rss/search?q={symbol.replace('.NS','')}+NSE+stock&hl=en-IN&gl=IN&ceid=IN:en"
        feed = feedparser.parse(url)
        return " | ".join([e.title for e in feed.entries[:2]]) if feed.entries else "No major news."
    except Exception: return "No major news."

# ==========================================
# 🕯️ CORE QUANT LOGIC
# ==========================================
def analyze_setup(df, nifty_trend_bullish):
    if df is None or len(df) < 50: return None
    def sf(val): return float(val.iloc[0]) if isinstance(val, pd.Series) else float(val)
    try:
        df = df.copy()
        close = df['Close']
        ltp = sf(close.iloc[-1])
        prev_close = sf(close.iloc[-2])
        if prev_close == 0: return None
        chg = round(((ltp - prev_close) / prev_close) * 100, 2)
        
        # RSI
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        loss_last = sf(loss.iloc[-1])
        rsi = 100.0 if loss_last == 0 else sf(100 - (100 / (1 + (sf(gain.iloc[-1]) / loss_last))))
        
        # VWAP
        tp = (df['High'] + df['Low'] + df['Close']) / 3
        vol_sum = sf(df['Volume'].rolling(20).sum().iloc[-1])
        if vol_sum == 0: return None
        vwap = sf((tp * df['Volume']).rolling(20).sum().iloc[-1]) / vol_sum
        
        # Pivot
        high, low = sf(df['High'].iloc[-1]), sf(df['Low'].iloc[-1])
        pivot = (high + low + ltp) / 3
        
        # SMC Order Block
        df['Body'] = abs(df['Close'] - df['Open'])
        ob = df.tail(15).sort_values(by='Body', ascending=False).iloc[0]
        ob_low = sf(min(ob['Open'], ob['Close']))
        
        # Bullish Candle
        c2, c3 = df.iloc[-2], df.iloc[-1]
        def parts(c):
            body = abs(sf(c['Close']) - sf(c['Open']))
            up = sf(c['High']) - max(sf(c['Close']), sf(c['Open']))
            low = min(sf(c['Close']), sf(c['Open'])) - sf(c['Low'])
            return body, up, low, sf(c['Close']) > sf(c['Open'])
        b3, u3, l3, g3 = parts(c3)
        is_bullish_candle = (g3 and sf(c3['Close']) > sf(c2['Close'])) or (l3 > (2 * b3) and u3 < b3)
        
        # Volume Spike
        vol_spike = sf(df['Volume'].iloc[-1]) > sf(df['Volume'].rolling(20).mean().iloc[-1]) * 1.5
        
        # Scoring
        score = 0; reasons = []
        if 40 < rsi < 70: score += 2; reasons.append("RSI Bullish Zone")
        elif rsi <= 40: score += 3; reasons.append("RSI Oversold Reversal")
        if ltp > vwap: score += 2; reasons.append("Price Above VWAP")
        if ltp > pivot: score += 1; reasons.append("Above Daily Pivot")
        if vol_spike: score += 2; reasons.append("Institutional Volume Spike")
        if sf(ob['Close']) > sf(ob['Open']): score += 1; reasons.append("SMC Demand Order Block")
        if is_bullish_candle: score += 2; reasons.append("Bullish Candlestick Pattern")

        min_score = 6 if nifty_trend_bullish else 7
        df['TR'] = np.maximum(df['High'] - df['Low'], np.maximum(abs(df['High'] - df['Close'].shift()), abs(df['Low'] - df['Close'].shift())))
        atr = sf(df['TR'].rolling(14).mean().iloc[-1])
        
        if score >= min_score:
            entry = round(ltp, 1)
            sl = round(min(ob_low, pivot) - (0.2 * atr), 1)
            t1 = round(entry + (1.5 * atr), 1)
            t2 = round(entry + (3.0 * atr), 1)
            
            # RRR Check (Risk Reward Ratio)
            risk = entry - sl
            reward = t1 - entry
            if risk <= 0 or (reward / risk) < 1.4: return None
        else: return None

        tag = "🔴 PENNY" if ltp < 50 else "🟡 SMALL" if ltp < 500 else "🟢 MID" if ltp < 2000 else "💎 LARGE"
        
        verdict = "Strong setup with " + " + ".join(reasons) + "."
        return {"ltp": ltp, "chg": chg, "tag": tag, "score": score, "reasons": verdict, "entry": entry, "sl": sl, "t1": t1, "t2": t2}
    except Exception: return None

# ==========================================
# 📅 FULL REPORT GENERATOR
# ==========================================
async def generate_full_report(is_tomorrow=False):
    start_time = time.time()
    
    # 🛡️ Safe Nifty Download (Fix for Series Error)
    nifty = await asyncio.to_thread(yf.download, "^NSEI", period="1mo", progress=False)
    nifty_bullish = True
    if not nifty.empty:
        try:
            close_series = nifty['Close']
            if isinstance(close_series, pd.DataFrame): close_series = close_series.iloc[:, 0]
            nifty_close = float(close_series.iloc[-1])
            nifty_sma20 = float(close_series.rolling(20).mean().iloc[-1])
            nifty_bullish = nifty_close >= nifty_sma20
        except Exception:
            pass

    symbols = await get_dynamic_universe()
    all_bulls = []
    
    # Batch Processing (40 stocks at a time)
    for i in range(0, len(symbols), 40):
        batch = symbols[i:i+40]
        try:
            data = await asyncio.to_thread(yf.download, batch, period="3mo", group_by="ticker", threads=True, progress=False)
            if data is not None and not data.empty:
                level0 = data.columns.get_level_values(0)
                for sym in batch:
                    if sym in level0:
                        res = analyze_setup(data[sym].dropna(), nifty_bullish)
                        if res:
                            res["symbol"] = sym.replace(".NS", "")
                            all_bulls.append(res)
        except Exception: pass
        await asyncio.sleep(1.0) # Prevent Yahoo Rate Limits
    
    gc.collect() # Free RAM

    if not all_bulls:
        return "⚠️ <b>No A+ High-RRR setups found. Market conditions might be flat or choppy.</b>"

    all_bulls.sort(key=lambda x: x["score"], reverse=True)
    top_5 = all_bulls[:5]
    duration = round(time.time() - start_time, 1)

    header = "TOMORROW'S PLAN" if is_tomorrow else "TODAY'S SETUPS"
    trend_status = "🟢 Nifty Bullish Trend" if nifty_bullish else "🟡 Nifty Defensive/Consolidation"
    
    report = f"<b>👁️ THE HORUS EYE - {header}</b>\n"
    report += f"<i>{datetime.now(IST).strftime('%d %b %Y | %I:%M %p')} IST</i> | ⏱️ <i>{duration}s</i>\n"
    report += f"<i>Market State: {trend_status}</i>\n{DIVIDER}\n\n"
    
    for s in top_5:
        # Future Custom API integration
        custom_data = await fetch_custom_data(s['symbol'])
        if custom_data: s['reasons'] += f" | {custom_data}"
        
        report += f"{s['tag']} <b>{s['symbol']}</b> | <code>₹{s['ltp']}</code> (<code>+{s['chg']}%</code>)\n"
        report += f"🧠 <b>Quant Logic:</b> <i>{s['reasons']}</i>\n"
        report += f"🟢 <b>Entry:</b> <code>₹{s['entry']}</code> | 🎯 <b>T1:</b> <code>₹{s['t1']}</code> | 🛑 <b>SL:</b> <code>₹{s['sl']}</code>\n\n"

    return report

# ==========================================
# 🚀 TELEGRAM COMMANDS
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📊 Today's Setups", callback_data="today"),
         InlineKeyboardButton("📈 Tomorrow's Plan", callback_data="tomorrow")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_html(
        f"<b>👁️ THE HORUS EYE PRO BOT</b>\n{DIVIDER}\n"
        f"Professional Nifty 500 SMC Scanner.\n"
        f"Select an action below:",
        reply_markup=reply_markup
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "today":
        await query.edit_message_text("<i>⏳ Scanning Nifty 500... Please wait (1-2 mins).</i>", parse_mode='HTML')
        report = await generate_full_report(is_tomorrow=False)
        keyboard = [[InlineKeyboardButton("🔄 Refresh Scan", callback_data="today")]]
        
        # Chunking logic for buttons
        if len(report) > 4000:
            chunks = [report[i:i+4000] for i in range(0, len(report), 4000)]
            await query.edit_message_text(chunks[0], parse_mode='HTML')
            for chunk in chunks[1:-1]:
                await context.bot.send_message(chat_id=query.message.chat_id, text=chunk, parse_mode='HTML')
            await context.bot.send_message(chat_id=query.message.chat_id, text=chunks[-1], parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await query.edit_message_text(report, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        
    elif query.data == "tomorrow":
        await query.edit_message_text("<i>⏳ Analyzing Tomorrow's Plan... Please wait (1-2 mins).</i>", parse_mode='HTML')
        report = await generate_full_report(is_tomorrow=True)
        keyboard = [[InlineKeyboardButton("🔄 Refresh Plan", callback_data="tomorrow")]]
        
        if len(report) > 4000:
            chunks = [report[i:i+4000] for i in range(0, len(report), 4000)]
            await query.edit_message_text(chunks[0], parse_mode='HTML')
            for chunk in chunks[1:-1]:
                await context.bot.send_message(chat_id=query.message.chat_id, text=chunk, parse_mode='HTML')
            await context.bot.send_message(chat_id=query.message.chat_id, text=chunks[-1], parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await query.edit_message_text(report, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_html("<i>⏳ Scanning Nifty 500... Please wait (1-2 mins).</i>")
    report = await generate_full_report(is_tomorrow=False)
    keyboard = [[InlineKeyboardButton("🔄 Refresh Scan", callback_data="today")]]
    
    if len(report) > 4000:
        chunks = [report[i:i+4000] for i in range(0, len(report), 4000)]
        await msg.edit_text(chunks[0], parse_mode='HTML')
        for chunk in chunks[1:-1]:
            await update.message.reply_html(chunk)
        await update.message.reply_html(chunks[-1], reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await msg.edit_text(report, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

async def tomorrow_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_html("<i>⏳ Analyzing for Tomorrow... Please wait (1-2 mins).</i>")
    report = await generate_full_report(is_tomorrow=True)
    keyboard = [[InlineKeyboardButton("🔄 Refresh Plan", callback_data="tomorrow")]]
    
    if len(report) > 4000:
        chunks = [report[i:i+4000] for i in range(0, len(report), 4000)]
        await msg.edit_text(chunks[0], parse_mode='HTML')
        for chunk in chunks[1:-1]:
            await update.message.reply_html(chunk)
        await update.message.reply_html(chunks[-1], reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await msg.edit_text(report, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

# ==========================================
# ⏰ AUTO-PILOT SCHEDULES (With Chunking Bug Fix)
# ==========================================
async def auto_morning(context: ContextTypes.DEFAULT_TYPE):
    if datetime.now(IST).weekday() > 4: return
    try:
        report = await generate_full_report(is_tomorrow=False)
        text = "🌅 <b>TODAY'S PLAN</b>\n\n" + report
        keyboard = [[InlineKeyboardButton("🔄 Refresh Scan", callback_data="today")]]
        
        if len(text) > 4000:
            chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
            for chunk in chunks[:-1]:
                await context.bot.send_message(chat_id=YOUR_CHAT_ID, text=chunk, parse_mode='HTML')
            await context.bot.send_message(chat_id=YOUR_CHAT_ID, text=chunks[-1], parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await context.bot.send_message(chat_id=YOUR_CHAT_ID, text=text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception: pass

async def auto_evening(context: ContextTypes.DEFAULT_TYPE):
    if datetime.now(IST).weekday() > 4: return
    try:
        report = await generate_full_report(is_tomorrow=True)
        text = "🌇 <b>TOMORROW'S PLAN</b>\n\n" + report
        keyboard = [[InlineKeyboardButton("🔄 Refresh Plan", callback_data="tomorrow")]]
        
        if len(text) > 4000:
            chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
            for chunk in chunks[:-1]:
                await context.bot.send_message(chat_id=YOUR_CHAT_ID, text=chunk, parse_mode='HTML')
            await context.bot.send_message(chat_id=YOUR_CHAT_ID, text=chunks[-1], parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await context.bot.send_message(chat_id=YOUR_CHAT_ID, text=text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception: pass

# ==========================================
# ⚡ MAIN ENTRY POINT
# ==========================================
if __name__ == '__main__':
    threading.Thread(target=start_health_server, daemon=True).start()
    
    while True:
        try:
            app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
            app.add_handler(CommandHandler("start", start))
            app.add_handler(CommandHandler("today", today_command))
            app.add_handler(CommandHandler("tomorrow", tomorrow_command))
            app.add_handler(CallbackQueryHandler(button_handler))
            
            jq = app.job_queue
            if jq:
                # 9:45 AM और 4:00 PM पर ऑटो-रिपोर्ट
                jq.run_daily(auto_morning, time=dt_time(hour=9, minute=45, tzinfo=IST))
                jq.run_daily(auto_evening, time=dt_time(hour=16, minute=0, tzinfo=IST))
                
            print("👁️ The Horus Eye Pro Trading Bot is Live (Pure Quant)...")
            app.run_polling(drop_pending_updates=True)
        except Exception as e:
            print(f"⚠️ Restarting due to exception: {e}")
            time.sleep(10)
            continue
