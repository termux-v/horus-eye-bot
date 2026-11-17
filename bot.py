import os
import asyncio
import logging
import httpx
import yfinance as yf
import pandas as pd
import numpy as np
import time
import gc
from datetime import time as dt_time, datetime
import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# ==========================================
# ⚙️ SYSTEM CONFIGURATION & TOKENS
# ==========================================
TELEGRAM_TOKEN = "9057274095:AAFUICR6sV4j60bViAheeKn7MLYzSkxpr70".strip()
YOUR_CHAT_ID = "6082045625".strip()

IST = pytz.timezone('Asia/Kolkata')
DIVIDER = "━━━━━━━━━━━━━━━━━━━━━━━"

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ==========================================
# 🛡️ 1000x BULLETPROOF ERROR HANDLER
# ==========================================
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(msg="Exception caught in application:", exc_info=context.error)
    try:
        if isinstance(update, Update) and update.effective_message:
            await update.effective_message.reply_text("⚠️ <b>Auto-Healed:</b> Minor network or data glitch bypassed smoothly.")
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
            logger.warning(f"Message send attempt {attempt+1} failed: {e}")
            await asyncio.sleep(1)
    return None

# ==========================================
# 🌐 DYNAMIC UNIVERSE & SECTOR MAPPER
# ==========================================
async def get_universe_with_sectors():
    sector_map = {}
    for attempt in range(2):
        try:
            url = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(url, headers=headers)
                if res.status_code == 200:
                    lines = res.text.split('\n')
                    for line in lines[1:]:
                        parts = line.split(',')
                        if len(parts) > 2 and parts[2].strip():
                            sym = parts[2].strip() + ".NS"
                            sec = parts[1].strip() if len(parts) > 1 and parts[1].strip() else "General"
                            sec = sec.replace(" Services", "").replace(" & ", "/").title()
                            sector_map[sym] = sec
                    if len(sector_map) > 100:
                        return sector_map
        except Exception:
            await asyncio.sleep(1)
            
    return {
        "RELIANCE.NS": "Oil/Gas", "ONGC.NS": "Oil/Gas", "BPCL.NS": "Oil/Gas", "IOC.NS": "Oil/Gas", "GAIL.NS": "Oil/Gas",
        "TCS.NS": "IT", "INFY.NS": "IT", "HCLTECH.NS": "IT", "WIPRO.NS": "IT", "TECHM.NS": "IT", "PERSISTENT.NS": "IT", "COFORGE.NS": "IT",
        "HDFCBANK.NS": "Financials", "ICICIBANK.NS": "Financials", "SBIN.NS": "Financials", "KOTAKBANK.NS": "Financials", "AXISBANK.NS": "Financials", "BAJFINANCE.NS": "Financials", "PFC.NS": "Financials", "RECLTD.NS": "Financials", "IRFC.NS": "Financials",
        "MARUTI.NS": "Automobile", "TATAMOTORS.NS": "Automobile", "M&M.NS": "Automobile", "EICHERMOT.NS": "Automobile", "HEROMOTOCO.NS": "Automobile",
        "SUNPHARMA.NS": "Healthcare", "LUPIN.NS": "Healthcare", "AUROPHARMA.NS": "Healthcare", "BIOCON.NS": "Healthcare", "ALKEM.NS": "Healthcare", "TORNTPHARM.NS": "Healthcare",
        "TATASTEEL.NS": "Metals", "JSWSTEEL.NS": "Metals", "HINDALCO.NS": "Metals", "VEDL.NS": "Metals", "SAIL.NS": "Metals", "NMDC.NS": "Metals",
        "ITC.NS": "FMCG", "HINDUNILVR.NS": "FMCG", "NESTLEIND.NS": "FMCG", "TITAN.NS": "Consumer", "TRENT.NS": "Consumer", "ZOMATO.NS": "Consumer", "PAYTM.NS": "Consumer", "IRCTC.NS": "Consumer",
        "LT.NS": "Capital Goods", "HAL.NS": "Capital Goods", "BEL.NS": "Capital Goods", "SIEMENS.NS": "Capital Goods", "ABB.NS": "Capital Goods", "CUMMINSIND.NS": "Capital Goods", "BHEL.NS": "Capital Goods",
        "NTPC.NS": "Power", "POWERGRID.NS": "Power", "TATAPOWER.NS": "Power", "ADANIPOWER.NS": "Power", "SUZLON.NS": "Power",
        "BHARTIARTL.NS": "Telecom", "DLF.NS": "Realty", "GODREJPROP.NS": "Realty", "ULTRACEMCO.NS": "Construction", "GRASIM.NS": "Construction"
    }

# ==========================================
# 🕯️ ULTRA-FAST QUANT ENGINE (SMC + VWAP + ATR)
# ==========================================
def analyze_setup(df, nifty_trend_bullish, sector_name, is_tomorrow=False):
    if df is None or len(df) < 30: return None
    def sf(val): 
        try:
            return float(val.iloc[0]) if isinstance(val, pd.Series) else float(val)
        except Exception:
            return 0.0
            
    try:
        df = df.dropna().copy()
        if len(df) < 20: return None
        
        close = df['Close']
        if isinstance(close, pd.DataFrame): close = close.iloc[:, 0]
        
        ltp = sf(close.iloc[-1])
        prev_close = sf(close.iloc[-2])
        if prev_close <= 0 or ltp <= 0: return None
        
        chg = round(((ltp - prev_close) / prev_close) * 100, 2)
        is_up_today = ltp > prev_close
        
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14, min_periods=1).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14, min_periods=1).mean()
        loss_last = sf(loss.iloc[-1])
        gain_last = sf(gain.iloc[-1])
        rsi = 100.0 if loss_last == 0 else sf(100 - (100 / (1 + (gain_last / loss_last))))
        
        high_s = df['High'].iloc[:, 0] if isinstance(df['High'], pd.DataFrame) else df['High']
        low_s = df['Low'].iloc[:, 0] if isinstance(df['Low'], pd.DataFrame) else df['Low']
        vol_s = df['Volume'].iloc[:, 0] if isinstance(df['Volume'], pd.DataFrame) else df['Volume']
        
        tp = (high_s + low_s + close) / 3
        vol_sum = sf(vol_s.rolling(20, min_periods=1).sum().iloc[-1])
        if vol_sum == 0: return {"is_up": is_up_today, "chg": chg, "setup": None}
        vwap = sf((tp * vol_s).rolling(20, min_periods=1).sum().iloc[-1]) / vol_sum
        
        high, low = sf(high_s.iloc[-1]), sf(low_s.iloc[-1])
        pivot = (high + low + ltp) / 3
        
        open_s = df['Open'].iloc[:, 0] if isinstance(df['Open'], pd.DataFrame) else df['Open']
        body_s = abs(close - open_s)
        
        temp_df = pd.DataFrame({'Close': close, 'Open': open_s, 'Body': body_s})
        ob = temp_df.tail(15).sort_values(by='Body', ascending=False).iloc[0]
        ob_low = sf(min(ob['Open'], ob['Close']))
        
        c2_close, c3_close = sf(close.iloc[-2]), sf(close.iloc[-1])
        c3_open = sf(open_s.iloc[-1])
        c3_high, c3_low = sf(high_s.iloc[-1]), sf(low_s.iloc[-1])
        
        body3 = abs(c3_close - c3_open)
        up3 = c3_high - max(c3_close, c3_open)
        low3 = min(c3_close, c3_open) - c3_low
        green3 = c3_close > c3_open
        
        is_bullish_candle = (green3 and c3_close > c2_close) or (low3 > (2 * body3) and up3 < body3)
        
        day_range = high - low
        close_near_high = ((ltp - low) / day_range >= 0.75) if day_range > 0 else False
        vol_mean = sf(vol_s.rolling(20, min_periods=1).mean().iloc[-1])
        vol_spike = sf(vol_s.iloc[-1]) > (vol_mean * 1.5) if vol_mean > 0 else False
        
        score = 0; reasons = []
        if 40 < rsi < 70: score += 2; reasons.append("RSI Bullish")
        elif rsi <= 40: score += 3; reasons.append("RSI Reversal")
        if ltp > vwap: score += 2; reasons.append("Above VWAP")
        if ltp > pivot: score += 1; reasons.append("Above Pivot")
        if vol_spike: score += 2; reasons.append("Vol Spike")
        if sf(ob['Close']) > sf(ob['Open']): score += 1; reasons.append("Demand OB")
        if is_bullish_candle: score += 2; reasons.append("Bullish Candle")
        
        if is_tomorrow and close_near_high:
            score += 2
            reasons.append("High-Close Breakout")

        min_score = 6 if nifty_trend_bullish else 7
        
        tr = np.maximum(high_s - low_s, np.maximum(abs(high_s - close.shift()), abs(low_s - close.shift())))
        atr = sf(tr.rolling(14, min_periods=1).mean().iloc[-1])
        if atr <= 0: atr = ltp * 0.02
        
        setup_data = None
        if score >= min_score:
            entry = round(ltp, 1)
            sl = round(min(ob_low, pivot) - (0.2 * atr), 1)
            t1 = round(entry + (1.5 * atr), 1)
            t2 = round(entry + (3.0 * atr), 1)
            
            risk = entry - sl
            reward = t1 - entry
            if risk > 0 and (reward / risk) >= 1.4:
                tag = "🔴 Penny" if ltp < 50 else "🟡 Small" if ltp < 500 else "🟢 Mid" if ltp < 2000 else "💎 Large"
                verdict = " | ".join(reasons)
                setup_data = {
                    "ltp": ltp, "chg": chg, "tag": tag, "sector": sector_name,
                    "score": score, "reasons": verdict, "entry": entry, "sl": sl, "t1": t1, "t2": t2
                }
                
        return {"is_up": is_up_today, "chg": chg, "setup": setup_data}
    except Exception:
        return None

# ==========================================
# 📅 TURBO ASYNC PARALLEL SCANNER ENGINE
# ==========================================
async def generate_full_report(is_tomorrow=False):
    start_time = time.time()
    
    nifty_bullish = True
    for _ in range(2):
        try:
            nifty = await asyncio.to_thread(yf.download, "^NSEI", period="1mo", progress=False)
            if nifty is not None and not nifty.empty:
                close_series = nifty['Close']
                if isinstance(close_series, pd.DataFrame): close_series = close_series.iloc[:, 0]
                nifty_close = float(close_series.iloc[-1])
                nifty_sma20 = float(close_series.rolling(20, min_periods=1).mean().iloc[-1])
                nifty_bullish = nifty_close >= nifty_sma20
                break
        except Exception:
            await asyncio.sleep(0.5)

    sector_map = await get_universe_with_sectors()
    symbols = list(sector_map.keys())
    
    all_bulls = []
    sector_stats = {}
    semaphore = asyncio.Semaphore(5)

    async def process_batch(batch):
        async with semaphore:
            for attempt in range(2):
                try:
                    data = await asyncio.to_thread(yf.download, batch, period="3mo", group_by="ticker", threads=True, progress=False)
                    if data is not None and not data.empty:
                        level0 = data.columns.get_level_values(0) if isinstance(data.columns, pd.MultiIndex) else None
                        for sym in batch:
                            try:
                                sub_df = data[sym] if level0 is not None and sym in level0 else data
                                if sub_df is not None and not sub_df.empty:
                                    sec = sector_map.get(sym, "General")
                                    res = analyze_setup(sub_df.dropna(), nifty_bullish, sec, is_tomorrow)
                                    if res:
                                        if sec not in sector_stats:
                                            sector_stats[sec] = {"up": 0, "total": 0, "top_sym": "", "top_chg": -999.0}
                                        sector_stats[sec]["total"] += 1
                                        if res["is_up"]:
                                            sector_stats[sec]["up"] += 1
                                        if res["chg"] > sector_stats[sec]["top_chg"]:
                                            sector_stats[sec]["top_chg"] = res["chg"]
                                            sector_stats[sec]["top_sym"] = sym.replace(".NS", "")
                                        
                                        if res["setup"]:
                                            res["setup"]["symbol"] = sym.replace(".NS", "")
                                            all_bulls.append(res["setup"])
                            except Exception:
                                continue
                    del data
                    break
                except Exception:
                    await asyncio.sleep(1.0)

    batches = [symbols[i:i+30] for i in range(0, len(symbols), 30)]
    await asyncio.gather(*(process_batch(b) for b in batches))
    
    gc.collect()
    duration = round(time.time() - start_time, 1)

    header = "TOMORROW'S SECTOR & BREAKOUT OUTLOOK" if is_tomorrow else "DAILY SECTOR & STOCK INTELLIGENCE"
    trend_status = "🟢 Bullish Trend" if nifty_bullish else "🟡 Consolidation / Defensive"
    
    report = f"<b>👁️ THE HORUS EYE | QUANT ENGINE v3.0</b>\n"
    report += f"<code>📅 {datetime.now(IST).strftime('%d %b %Y | %I:%M %p')} IST | ⏱️ {duration}s (Turbo)</code>\n"
    report += f"<code>📊 Market State : {trend_status}</code>\n{DIVIDER}\n\n"
    
    report += "<b>📈 SECTOR BREADTH (UP / TOTAL):</b>\n"
    sorted_sectors = sorted(
        sector_stats.items(), 
        key=lambda x: (x[1]["up"] / x[1]["total"] if x[1]["total"] > 0 else 0), 
        reverse=True
    )
    
    bullish_sectors = []
    for sec_name, st in sorted_sectors:
        if st["total"] > 0:
            pct = round((st["up"] / st["total"]) * 100)
            icon = "🟢" if pct >= 60 else "🟡" if pct >= 40 else "🔴"
            leader = f"| <b>{st['top_sym']}</b> (+{st['top_chg']}%)" if st['top_chg'] > 0 else ""
            report += f"{icon} <b>{sec_name:<13}:</b> {st['up']:2d}/{st['total']:2d} ({pct:2d}%){leader}\n"
            if pct >= 50:
                bullish_sectors.append(sec_name)
            
    report += f"\n{DIVIDER}\n\n"
    
    if not all_bulls:
        report += "⚠️ <b>No A+ High-RRR setups found right now. Market is consolidating.</b>"
        return report

    selected_stocks = []
    other_stocks = []
    
    for s in all_bulls:
        if s["sector"] in bullish_sectors[:3]:
            selected_stocks.append(s)
        else:
            other_stocks.append(s)

    selected_stocks.sort(key=lambda x: x["score"], reverse=True)
    other_stocks.sort(key=lambda x: x["score"], reverse=True)

    final_stocks = selected_stocks[:4] + other_stocks[:2]
    final_stocks = final_stocks[:5]

    sub_title = "🚀 <b>TOP BULLISH SECTOR PICKS (2-3 PER SECTOR):</b>\n\n" if is_tomorrow else "🔥 <b>HIGH-CONVICTION LEADING STOCKS:</b>\n\n"
    report += sub_title
    
    for idx, s in enumerate(final_stocks, 1):
        report += f"<b>{idx}. {s['symbol']}</b> [<i>{s['sector']}</i>] {s['tag']}\n"
        report += f"   <code>LTP: ₹{
  
