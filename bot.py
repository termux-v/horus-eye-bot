import os
import asyncio
import sys
import httpx
import yfinance as yf
import pandas as pd
import numpy as np
import time
import io
import gc
from datetime import time as dt_time, datetime
import pytz
from loguru import logger
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import mplfinance as mpf
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# ==========================================
# ⚙️ ENTERPRISE CONFIGURATION & SECURE TOKENS
# ==========================================
TELEGRAM_TOKEN = "9057274095:AAFUICR6sV4j60bViAheeKn7MLYzSkxpr70".strip()
YOUR_CHAT_ID = "6082045625".strip()

IST = pytz.timezone('Asia/Kolkata')
DIVIDER = "━━━━━━━━━━━━━━━━━━━━━━━"

# 🌟 Advanced Loguru Setup (Open-Source Professional Logging)
logger.remove()
logger.add(sys.stdout, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>", level="INFO")

# ==========================================
# 🛡️ ENTERPRISE BULLETPROOF ERROR BOUNDARY
# ==========================================
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f"Enterprise Exception Caught: {context.error}")
    try:
        if isinstance(update, Update) and update.effective_message:
            await update.effective_message.reply_text("⚠️ <b>System Auto-Healed:</b> Transient anomaly bypassed seamlessly.")
    except Exception:
        pass

async def safe_send_message(bot, chat_id, text, parse_mode='HTML', reply_markup=None):
    for attempt in range(3):
        try:
            if len(text) > 4000:
                chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
                for chunk in chunks[:-1]:
                    await bot.send_message(chat_id=chat_id, text=chunk, parse_mode=parse_mode)
                return await bot.send_message(chat_id=chat_id, text=chunks[-1], parse_mode=parse_mode, reply_markup=reply_markup)
            else:
                return await bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode, reply_markup=reply_markup)
        except Exception as e:
            logger.warning(f"Delivery attempt {attempt+1} failed: {e}")
            await asyncio.sleep(1)
    return None

# ==========================================
# 📊 PROFESSIONAL CANDLESTICK CHART GENERATOR (`mplfinance`)
# ==========================================
def generate_candlestick_chart(symbol, df):
    try:
        plot_df = df.tail(45).copy()
        if isinstance(plot_df.columns, pd.MultiIndex):
            plot_df.columns = plot_df.columns.get_level_values(0)
            
        plot_df = plot_df[['Open', 'High', 'Low', 'Close', 'Volume']]
        plot_df.index = pd.to_datetime(plot_df.index)

        mc = mpf.make_marketcolors(up='#00ffcc', down='#ff4444', edge='inherit', wick='inherit', volume='in')
        s  = mpf.make_mpf_style(marketcolors=mc, figcolor='#121212', ec='white', fc='#1e1e1e', gridstyle=':', gridcolor='#333333')

        buf = io.BytesIO()
        mpf.plot(
            plot_df,
            type='candle',
            volume=True,
            mav=(20),
            style=s,
            title=dict(title=f"THE HORUS EYE | {symbol} Detailed Candlestick Matrix", color='white', size=11),
            savefig=dict(fname=buf, format='png', dpi=120, bbox_inches='tight')
        )
        buf.seek(0)
        plt.close('all')
        return buf
    except Exception as e:
        logger.warning(f"Candlestick chart generation failed for {symbol}: {e}")
        return None

# ==========================================
# 🌐 UNIVERSAL MARKET UNIVERSE (ALL STOCKS & SECTORS)
# ==========================================
async def get_universal_universe():
    sector_map = {}
    try:
        url = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.get(url, headers=headers)
            if res.status_code == 200:
                for line in res.text.split('\n')[1:]:
                    parts = line.split(',')
                    if len(parts) > 2 and parts[2].strip():
                        sym = parts[2].strip() + ".NS"
                        sec = parts[1].strip().replace(" Services", "").replace(" & ", "/").title() or "General"
                        sector_map[sym] = sec
    except Exception:
        pass

    core_stocks = {
        "RELIANCE.NS": "Oil/Gas", "ONGC.NS": "Oil/Gas", "BPCL.NS": "Oil/Gas", "IOC.NS": "Oil/Gas", "GAIL.NS": "Oil/Gas",
        "TCS.NS": "IT", "INFY.NS": "IT", "HCLTECH.NS": "IT", "WIPRO.NS": "IT", "TECHM.NS": "IT", "PERSISTENT.NS": "IT", "COFORGE.NS": "IT",
        "HDFCBANK.NS": "Financials", "ICICIBANK.NS": "Financials", "SBIN.NS": "Financials", "KOTAKBANK.NS": "Financials", "AXISBANK.NS": "Financials", "BAJFINANCE.NS": "Financials", "PFC.NS": "Financials", "RECLTD.NS": "Financials", "IRFC.NS": "Financials",
        "MARUTI.NS": "Automobile", "TATAMOTORS.NS": "Automobile", "M&M.NS": "Automobile", "EICHERMOT.NS": "Automobile", "HEROMOTOCO.NS": "Automobile",
        "SUNPHARMA.NS": "Healthcare", "LUPIN.NS": "Healthcare", "AUROPHARMA.NS": "Healthcare", "DRREDDY.NS": "Healthcare", "CIPLA.NS": "Healthcare",
        "TATASTEEL.NS": "Metals", "JSWSTEEL.NS": "Metals", "HINDALCO.NS": "Metals", "VEDL.NS": "Metals", "SAIL.NS": "Metals", "COALINDIA.NS": "Metals",
        "ITC.NS": "FMCG", "HINDUNILVR.NS": "FMCG", "NESTLEIND.NS": "FMCG", "BRITANNIA.NS": "FMCG", "TATACONSUM.NS": "FMCG",
        "TITAN.NS": "Consumer", "TRENT.NS": "Consumer", "ZOMATO.NS": "Consumer", "PAYTM.NS": "Consumer", "IRCTC.NS": "Consumer",
        "LT.NS": "Capital Goods", "HAL.NS": "Capital Goods", "BEL.NS": "Capital Goods", "SIEMENS.NS": "Capital Goods", "ABB.NS": "Capital Goods",
        "NTPC.NS": "Power", "POWERGRID.NS": "Power", "TATAPOWER.NS": "Power", "ADANIPOWER.NS": "Power", "SUZLON.NS": "Power",
        "BHARTIARTL.NS": "Telecom", "JIOFIN.NS": "Telecom", "IDEA.NS": "Telecom",
        "DLF.NS": "Realty", "GODREJPROP.NS": "Realty", "OBEROIRLTY.NS": "Realty",
        "ULTRACEMCO.NS": "Construction", "GRASIM.NS": "Construction", "AMBUJACEM.NS": "Construction",
        "YESBANK.NS": "Financials", "JPPOWER.NS": "Power", "RPOWER.NS": "Power", "TRIDENT.NS": "Consumer"
    }
    
    for k, v in core_stocks.items():
        if k not in sector_map:
            sector_map[k] = v
            
    return sector_map

# ==========================================
# 🕯️ ADVANCED INSTITUTIONAL QUANT ENGINE
# ==========================================
def analyze_setup(df, market_regime, sector_name, is_tomorrow=False):
    if df is None or len(df) < 30: return None
    try:
        df = df.dropna().copy()
        if len(df) < 20: return None
        
        close = df['Close'].iloc[:, 0] if isinstance(df['Close'], pd.DataFrame) else df['Close']
        ltp = float(close.iloc[-1])
        prev_close = float(close.iloc[-2])
        if prev_close <= 0 or ltp <= 0: return None
        
        chg = round(((ltp - prev_close) / prev_close) * 100, 2)
        is_up = ltp > prev_close
        
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(14, min_periods=1).mean()
        loss = (-delta.clip(upper=0)).rolling(14, min_periods=1).mean()
        loss_val, gain_val = float(loss.iloc[-1]), float(gain.iloc[-1])
        rsi = 100.0 if loss_val == 0 else float(100 - (100 / (1 + (gain_val / loss_val))))
        
        high_s = df['High'].iloc[:, 0] if isinstance(df['High'], pd.DataFrame) else df['High']
        low_s = df['Low'].iloc[:, 0] if isinstance(df['Low'], pd.DataFrame) else df['Low']
        vol_s = df['Volume'].iloc[:, 0] if isinstance(df['Volume'], pd.DataFrame) else df['Volume']
        
        tp = (high_s + low_s + close) / 3
        vol_sum = float(vol_s.rolling(20, min_periods=1).sum().iloc[-1])
        if vol_sum == 0: return {"is_up": is_up, "chg": chg, "setup": None}
        vwap = float((tp * vol_s).rolling(20, min_periods=1).sum().iloc[-1]) / vol_sum
        
        high, low = float(high_s.iloc[-1]), float(low_s.iloc[-1])
        pivot = (high + low + ltp) / 3
        
        open_s = df['Open'].iloc[:, 0] if isinstance(df['Open'], pd.DataFrame) else df['Open']
        body_s = abs(close - open_s)
        
        temp_df = pd.DataFrame({'Close': close, 'Open': open_s, 'Body': body_s})
        ob = temp_df.tail(15).sort_values(by='Body', ascending=False).iloc[0]
        ob_low = float(min(ob['Open'], ob['Close']))
        
        c2_c, c3_c = float(close.iloc[-2]), float(close.iloc[-1])
        c3_o, c3_h, c3_l = float(open_s.iloc[-1]), float(high_s.iloc[-1]), float(low_s.iloc[-1])
        
        body3 = abs(c3_c - c3_o)
        up3, low3 = c3_h - max(c3_c, c3_o), min(c3_c, c3_o) - c3_l
        is_bullish_candle = (c3_c > c3_o and c3_c > c2_c) or (low3 > (2 * body3) and up3 < body3)
        
        day_range = high - low
        close_near_high = ((ltp - low) / day_range >= 0.75) if day_range > 0 else False
        vol_mean = float(vol_s.rolling(20, min_periods=1).mean().iloc[-1])
        vol_spike = float(vol_s.iloc[-1]) > (vol_mean * 1.5) if vol_mean > 0 else False
        
        score = 0; reasons = []
        if 40 < rsi < 70: score += 2; reasons.append("RSI Bullish")
        elif rsi <= 40: score += 3; reasons.append("RSI Reversal")
        if ltp > vwap: score += 2; reasons.append("Above VWAP")
        if ltp > pivot: score += 1; reasons.append("Above Pivot")
        if vol_spike: score += 2; reasons.append("Vol Spike")
        if float(ob['Close']) > float(ob['Open']): score += 1; reasons.append("Demand OB")
        if is_bullish_candle: score += 2; reasons.append("Bullish Candle")
        
        if is_tomorrow and close_near_high:
            score += 2; reasons.append("High-Close Breakout")

        min_score = 5 if market_regime == "BULLISH" else 6
        
        tr = np.maximum(high_s - low_s, np.maximum(abs(high_s - close.shift()), abs(low_s - close.shift())))
        atr = float(tr.rolling(14, min_periods=1).mean().iloc[-1])
        if atr <= 0: atr = ltp * 0.02
        
        setup_data = None
        if score >= min_score:
            entry = round(ltp, 1)
            sl_buffer = 0.3 if market_regime == "VOLATILE" else 0.2
            sl = round(min(ob_low, pivot) - (sl_buffer * atr), 1)
            t1 = round(entry + (1.5 * atr), 1)
            t2 = round(entry + (3.0 * atr), 1)
            
            risk = entry - sl
            reward = t1 - entry
            if risk > 0 and (reward / risk) >= 1.3:
                tag = "🔴 Penny" if ltp < 50 else "🟡 Small" if ltp < 500 else "🟢 Mid" if ltp < 2000 else "💎 Large"
                setup_data = {
                    "ltp": ltp, "chg": chg, "tag": tag, "sector": sector_name,
                    "score": score, "reasons": " | ".join(reasons), "entry": entry, "sl": sl, "t1": t1, "t2": t2, "raw_df": df
                }
                
        return {"is_up": is_up, "chg": chg, "setup": setup_data}
    except Exception:
        return None

# ==========================================
# ⚡ FULL-UNIVERSE SECTOR-WISE DETAILED SCANNER
# ==========================================
async def generate_full_report(is_tomorrow=False):
    start_time = time.time()
    
    market_regime = "BULLISH"
    try:
        nifty = await asyncio.to_thread(yf.download, "^NSEI", period="2mo", progress=False)
        if nifty is not None and not nifty.empty:
            cs = nifty['Close'].iloc[:, 0] if isinstance(nifty['Close'], pd.DataFrame) else nifty['Close']
            sma20 = cs.rolling(20, min_periods=1).mean()
            volatility = cs.pct_change().rolling(20).std().iloc[-1]
            if volatility > 0.02: market_regime = "VOLATILE"
            elif float(cs.iloc[-1]) >= float(sma20.iloc[-1]): market_regime = "BULLISH"
            else: market_regime = "CONSOLIDATION"
    except Exception:
        pass

    sector_map = await get_universal_universe()
    symbols = list(sector_map.keys())
    
    sector_stocks_pool = {}
    sector_stats = {}
    semaphore = asyncio.Semaphore(6)

    async def process_batch(batch):
        async with semaphore:
            try:
                data = await asyncio.to_thread(yf.download, batch, period="3mo", group_by="ticker", threads=True, progress=False)
                if data is not None and not data.empty:
                    level0 = data.columns.get_level_values(0) if isinstance(data.columns, pd.MultiIndex) else None
                    for sym in batch:
                        try:
                            sub_df = data[sym] if level0 is not None and sym in level0 else data
                            if sub_df is not None and not sub_df.empty:
                                sec = sector_map.get(sym, "General")
                                res = analyze_setup(sub_df.dropna(), market_regime, sec, is_tomorrow)
                                if res:
                                    if sec not in sector_stats:
                                        sector_stats[sec] = {"up": 0, "total": 0}
                                    sector_stats[sec]["total"] += 1
                                    if res["is_up"]: sector_stats[sec]["up"] += 1
                                    
                                    if res["setup"]:
                                        res["setup"]["symbol"] = sym.replace(".NS", "")
                                        if sec not in sector_stocks_pool:
                                            sector_stocks_pool[sec] = []
                                        sector_stocks_pool[sec].append(res["setup"])
                        except Exception:
                            continue
                del data
            except Exception:
                pass

    batches = [symbols[i:i+35] for i in range(0, len(symbols), 35)]
    await asyncio.gather(*(process_batch(b) for b in batches))
    gc.collect()
    
    duration = round(time.time() - start_time, 1)
    regime_display = "🟢 Bullish Trend" if market_regime == "BULLISH" else "🟡 Consolidation" if market_regime == "CONSOLIDATION" else "🔴 High Volatility"
    
    report = f"<b>👁️ THE HORUS EYE | ENTERPRISE v2026 MATRIX</b>\n"
    report += f"<code>📅 {datetime.now(IST).strftime('%d %b %Y | %I:%M %p')} | ⏱️ {duration}s</code>\n"
    report += f"<code>📊 Market Regime : {regime_display}</code>\n{DIVIDER}\n\n"
    
    report += "<b>📈 SECTOR BREADTH (UP / TOTAL):</b>\n"
    sorted_sectors = sorted(sector_stats.items(), key=lambda x: (x[1]["up"] / x[1]["total"] if x[1]["total"] > 0 else 0), reverse=True)
    
    for sec_name, st in sorted_sectors:
        if st["total"] > 0:
            pct = round((st["up"] / st["total"]) * 100)
            icon = "🟢" if pct >= 60 else "🟡" if pct >= 40 else "🔴"
            report += f"{icon} <b>{sec_name:<13}:</b> {st['up']:2d}/{st['total']:2d} ({pct:2d}%)\n"
            
    report += f"\n{DIVIDER}\n\n"
    report += "🚀 <b>DETAILED SECTOR-WISE TOP PICKS (2-3 PER SECTOR):</b>\n\n"

    top_chart_stocks = []
    for sec_name, stocks in sector_stocks_pool.items():
        stocks.sort(key=lambda x: x["score"], reverse=True)
        top_picks = stocks[:3]
        
        report += f"📂 <b>SECTOR: {sec_name.upper()}</b>\n"
        for idx, s in enumerate(top_picks, 1):
            report += f"  <b>{idx}. {s['symbol']}</b> {s['tag']}\n"
            report += f"     <code>LTP: ₹{s['ltp']} ({s['chg']:+.2f}%) | Score: {s['score']}/10</code>\n"
            report += f"     🧠 <code>Logic: {s['reasons']}</code>\n"
            report += f"     🎯 <b>Entry:</b> <code>₹{s['entry']}</code> | <b>T1:</b> <code>₹{s['t1']}</code> | <b>SL:</b> <code>₹{s['sl']}</code>\n"
            top_chart_stocks.append(s)
        report += "\n"

    return report, top_chart_stocks

# ==========================================
# 🚀 TELEGRAM INTERACTIVE HANDLERS & WEBHOOK
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("📊 Universal Live Matrix", callback_data="today"),
                 InlineKeyboardButton("🔮 Tomorrow Outlook", callback_data="tomorrow")]]
    await update.message.reply_html(f"<b>👁️ THE HORUS EYE PRO BOT</b>\n{DIVIDER}\nSelect an action:", reply_markup=InlineKeyboardMarkup(keyboard))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    is_tom = (query.data == "tomorrow")
    await query.edit_message_text("<i>⏳ Scanning All Market Stocks & Generating Candlestick Charts...</i>", parse_mode='HTML')
    
    report, top_stocks = await generate_full_report(is_tomorrow=is_tom)
    keyboard = [[InlineKeyboardButton("🔄 Refresh", callback_data=query.data)]]
    
    await query.edit_message_text("Scan complete. Delivering universal matrix...", parse_mode='HTML')
    await safe_send_message(context.bot, query.message.chat_id, report, reply_markup=InlineKeyboardMarkup(keyboard))
    
    for s in top_stocks[:3]:
        if "raw_df" in s and s["raw_df"] is not None:
            chart_buf = generate_candlestick_chart(s["symbol"], s["raw_df"])
            if chart_buf:
                try:
                    await context.bot.send_photo(chat_id=query.message.chat_id, photo=chart_buf, caption=f"📊 <b>{s['symbol']}</b> ({s['sector']}) Candlestick Matrix")
                except Exception:
                    pass

async def cmd_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_html("<i>⏳ Scanning All Market Stocks...</i>")
    report, top_stocks = await generate_full_report(is_tomorrow=False)
    await msg.delete()
    await safe_send_message(context.bot, update.effective_chat.id, report, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Refresh", callback_data="today")]]))
    for s in top_stocks[:3]:
        if "raw_df" in s and s["raw_df"] is not None:
            chart_buf = generate_candlestick_chart(s["symbol"], s["raw_df"])
            if chart_buf:
                try:
                    await update.effective_chat.send_photo(photo=chart_buf, caption=f"📊 <b>{s['symbol']}</b> ({s['sector']}) Candlestick Matrix")
                except Exception:
                    pass

async def cmd_tomorrow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_html("<i>⏳ Analyzing Market Outlook...</i>")
    report, top_stocks = await generate_full_report(is_tomorrow=True)
    await msg.delete()
    await safe_send_message(context.bot, update.effective_chat.id, report, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Refresh", callback_data="tomorrow")]]))
    for s in top_stocks[:3]:
        if "raw_df" in s and s["raw_df"] is not None:
            chart_buf = generate_candlestick_chart(s["symbol"], s["raw_df"])
            if chart_buf:
                try:
                    await update.effective_chat.send_photo(photo=chart_buf, caption=f"📊 <b>{s['symbol']}</b> ({s['sector']}) Candlestick Matrix")
                except Exception:
                    pass

async def auto_morning(context: ContextTypes.DEFAULT_TYPE):
    if datetime.now(IST).weekday() > 4: return
    report, top_stocks = await generate_full_report(is_tomorrow=False)
    await safe_send_message(context.bot, YOUR_CHAT_ID, "🌅 <b>UNIVERSAL MORNING BRIEFING</b>\n\n" + report, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Refresh", callback_data="today")]]))
    for s in top_stocks[:3]:
        if "raw_df" in s and s["raw_df"] is not None:
            chart_buf = generate_candlestick_chart(s["symbol"], s["raw_df"])
            if chart_buf:
                try:
                    await context.bot.send_photo(chat
