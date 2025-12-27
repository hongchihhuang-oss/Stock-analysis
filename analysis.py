import yfinance as yf
import pandas as pd
import requests
import ta
import datetime
import time
import twstock
import numpy as np
from bs4 import BeautifulSoup

# 🟢 版本號
APP_VERSION = "v12.0 (首席分析師旗艦版)"

# ==========================================
# 1. 宏觀戰情室 (Macro War Room)
# ==========================================
def get_macro_context():
    print("🌍 正在研判全球總經局勢...")
    context = {"Trend": "盤整", "Score": 50, "Details": []}
    
    try:
        # 抓取關鍵指數: 台股, 費半, 台幣, VIX
        tickers = ["^TWII", "^SOX", "TWD=X", "^VIX"]
        df = yf.download(tickers, period="6mo", progress=False)['Close']
        
        # 1. 台股趨勢 (TWII)
        twii = df['^TWII']
        twii_now = twii.iloc[-1]
        twii_ma20 = twii.tail(20).mean()
        twii_ma60 = twii.tail(60).mean()
        
        twii_signal = "偏多" if twii_now > twii_ma20 else "偏空"
        context['Details'].append(f"台股技術面: {twii_signal} (月線之上:{twii_now > twii_ma20})")
        
        # 2. 資金流向 (USD/TWD)
        # 台幣貶值(數值變大) = 外資匯出 = 空
        usd = df['TWD=X']
        usd_ma5 = usd.tail(5).mean()
        usd_now = usd.iloc[-1]
        
        fund_flow = "外資匯入(多)" if usd_now < usd_ma5 else "外資匯出(空)"
        context['Details'].append(f"資金動能: {fund_flow} (匯率:{round(usd_now,2)})")
        
        # 3. 恐慌指數 (VIX)
        vix = df['^VIX'].iloc[-1]
        sentiment = "市場安穩" if vix < 20 else "市場恐慌"
        context['Details'].append(f"市場情緒: {sentiment} (VIX:{round(vix,1)})")
        
        # 4. 費半指引 (SOX)
        sox = df['^SOX']
        sox_trend = "強勢" if sox.iloc[-1] > sox.tail(10).mean() else "弱勢"
        context['Details'].append(f"半導體風向: {sox_trend}")

        # 綜合評分 (0-100)
        score = 50
        if twii_now > twii_ma20: score += 15
        if twii_now > twii_ma60: score += 10
        if usd_now < usd_ma5: score += 15 # 台幣升值加分
        if vix < 20: score += 10
        if sox_trend == "強勢": score += 10
        
        context['Score'] = score
        if score >= 75: context['Trend'] = "🚀 多頭順風 (Aggressive)"
        elif score >= 50: context['Trend'] = "⚖️ 震盪盤整 (Neutral)"
        else: context['Trend'] = "🛡️ 空頭防守 (Defensive)"
        
    except Exception as e:
        print(f"Macro Error: {e}")
        context['Details'].append("無法取得總經數據")
        
    return context

# ==========================================
# 2. 個股深度分析 (Deep Dive)
# ==========================================
def get_volume_leaders():
    # 抓取熱門前 10 檔
    leaders = []
    try:
        url = "https://tw.stock.yahoo.com/rank/turnover?exchange=TAI"
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers)
        soup = BeautifulSoup(r.text, 'html.parser')
        for link in soup.find_all('a', href=True):
            if "/quote/" in link['href'] and ".TW" in link['href']:
                ticker = link['href'].split("/quote/")[-1]
                if ticker not in leaders:
                    leaders.append(ticker)
                    if len(leaders) >= 10: break
    except: leaders = ['2330.TW', '2317.TW', '2603.TW', '2454.TW']
    return leaders

def analyze_stock(ticker, macro_trend):
    try:
        # 下載資料
        df = yf.download(ticker, period="1y", progress=False)
        if df.empty or len(df) < 60: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        
        # 下載大盤資料做 RS 比較
        twii = yf.download("^TWII", period="1y", progress=False)['Close']
        
        # === A. 技術面 (Technical) ===
        close = df['Close']
        ma5 = close.rolling(5).mean()
        ma20 = close.rolling(20).mean()
        ma60 = close.rolling(60).mean()
        
        # 布林通道 (Bollinger Bands)
        std20 = close.rolling(20).std()
        upper = ma20 + (std20 * 2)
        lower = ma20 - (std20 * 2)
        bb_width = (upper - lower) / ma20 # 通道寬度 (壓縮判斷)
        
        # KD 指標
        stoch = ta.momentum.StochasticOscillator(df['High'], df['Low'], close)
        k_val = stoch.stoch().iloc[-1]
        
        # RSI
        rsi = ta.momentum.RSIIndicator(close, 14).rsi().iloc[-1]

        # === B. 籌碼/強度 (Strength) ===
        # 相對強弱 (RS): 個股漲跌幅 - 大盤漲跌幅 (近5日)
        stock_ret = (close.iloc[-1] - close.iloc[-6]) / close.iloc[-6]
        try:
            market_ret = (twii.iloc[-1] - twii.iloc[-6]) / twii.iloc[-6]
            rs_rating = stock_ret - market_ret # 正值代表強於大盤
        except: rs_rating = 0
        
        # === C. 風報比 (Risk/Reward) ===
        price = float(close.iloc[-1])
        # 找近 60 日支撐壓力
        recent_high = float(df['High'].tail(60).max())
        recent_low = float(df['Low'].tail(60).min())
        
        dist_to_resistance = (recent_high - price) / price
        dist_to_support = (price - recent_low) / price
        rr_ratio = dist_to_resistance / dist_to_support if dist_to_support > 0 else 0
        
        # === D. 總結訊號 (Verdict) ===
        signals = []
        verdict = "觀望"
        verdict_color = "#95a5a6"
        score = 0
        
        # 評分邏輯
        if price > ma20.iloc[-1]: score += 20; signals.append("站上月線")
        if price > ma60.iloc[-1]: score += 20; signals.append("多頭排列")
        if rs_rating > 0: score += 20; signals.append("強於大盤")
        if bb_width.iloc[-1] < 0.10: signals.append("布林壓縮中(待變盤)")
        if k_val < 20: signals.append("KD超賣(反彈機會)")
        if rr_ratio > 2: score += 10; signals.append("風報比佳")
        
        if score >= 60: 
            verdict = "建議佈局"
            verdict_color = "#f39c12"
        if score >= 80:
            verdict = "強力買進"
            verdict_color = "#e74c3c"
        if price < ma20.iloc[-1] and price < ma60.iloc[-1]:
            verdict = "趨勢翻空"
            verdict_color = "#2ecc71" # 綠色
            
        # === E. 基本面 & 新聞 ===
        info = yf.Ticker(ticker).info
        fund = {
            "PE": info.get('trailingPE', 'N/A'),
            "EPS": info.get('trailingEps', 'N/A'),
            "RevGrowth": info.get('revenueGrowth', 0)
        }
        
        # 取得新聞
        news_titles = []
        try:
            r = requests.get(f"https://tw.stock.yahoo.com/quote/{ticker}/news", headers={'User-Agent': 'Mozilla/5.0'})
            soup = BeautifulSoup(r.text, 'html.parser')
            for t in soup.find_all('h3', limit=3):
                if t.find('a'): news_titles.append(t.find('a').text)
        except: pass
        
        # 取得名稱
        name = ticker
        try:
            if ticker.split('.')[0] in twstock.codes:
                name = twstock.codes[ticker.split('.')[0]].name
        except: pass

        return {
            "id": ticker, "name": name,
            "price": round(price, 2), 
            "change": round((price - df['Close'].iloc[-2])/df['Close'].iloc[-2]*100, 2),
            "verdict": verdict, "verdict_color": verdict_color, "score": score,
            "signals": signals,
            "tech": {
                "rsi": round(rsi, 1), "k": round(k_val, 1),
                "bb_pos": "上緣" if price > upper.iloc[-1] else ("下緣" if price < lower.iloc[-1] else "中軌"),
                "ma_align": "多頭" if ma5.iloc[-1]>ma20.iloc[-1]>ma60.iloc[-1] else "整理"
            },
            "chips": {
                "rs_val": round(rs_rating*100, 2), # RS值
                "status": "強勢吸金" if rs_rating > 0.02 else ("弱勢" if rs_rating < -0.02 else "隨大盤")
            },
            "rr": {
                "upside": round(dist_to_resistance*100, 1),
                "downside": round(dist_to_support*100, 1),
                "ratio": round(rr_ratio, 2)
            },
            "fund": fund, "news": news_titles
        }
    except Exception as e:
        print(f"Error {ticker}: {e}")
        return None

# === 主程式執行 ===
macro = get_macro_context()
stocks = get_volume_leaders()
results = []

print(f"首席分析師正在掃描 {len(stocks)} 檔標的...")
for s in stocks:
    res = analyze_stock(s, macro['Trend'])
    if res: results.append(res)

# 排序: 分數高 -> 低
results.sort(key=lambda x: x['score'], reverse=True)

# === HTML 產出 (Bloomberg Style) ===
html = f"""
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Pro Analyst {APP_VERSION}</title>
    <style>
        :root {{ --bg: #121212; --card-bg: #1e1e1e; --text: #e0e0e0; --accent: #bb86fc; --up: #ff4d4d; --down: #00b894; }}
        body {{ background: var(--bg); color: var(--text); font-family: 'Helvetica Neue', Arial, sans-serif; margin: 0; padding-bottom: 50px; }}
        
        /* 1. 宏觀戰情室 Header */
        .macro-header {{ background: linear-gradient(180deg, #2c3e50 0%, #121212 100%); padding: 20px; text-align: center; border-bottom: 2px solid #333; }}
        .macro-score {{ font-size: 3em; font-weight: 900; color: { "#ff4d4d" if macro['Score'] >= 50 else "#00b894" }; margin: 10px 0; }}
        .macro-trend {{ font-size: 1.2em; font-weight: bold; background: rgba(255,255,255,0.1); display: inline-block; padding: 5px 15px; border-radius: 20px; }}
        .macro-list {{ text-align: left; margin-top: 15px; font-size: 0.9em; color: #bbb; line-height: 1.6; display: inline-block; }}
        
        /* 2. 個股卡片 (Pro Report Card) */
        .report-card {{ background: var(--card-bg); margin: 20px 15px; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.5); border: 1px solid #333; }}
        
        /* Header: Name & Verdict */
        .card-header {{ padding: 15px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #333; }}
        .stock-title h1 {{ margin: 0; font-size: 1.5em; }}
        .stock-title span {{ color: #888; font-size: 0.9em; }}
        .verdict-badge {{ font-size: 0.9em; font-weight: bold; padding: 5px 10px; border-radius: 4px; color: #121212; }}
        
        /* Price Section */
        .price-sec {{ padding: 15px; display: flex; align-items: baseline; }}
        .big-price {{ font-size: 2.5em; font-weight: 800; }}
        .price-change {{ font-size: 1.2em; margin-left: 10px; font-weight: bold; }}
        .up {{ color: var(--up); }} .down {{ color: var(--down); }}
        
        /* Analysis Grid (4 Quadrants) */
        .analysis-grid {{ display: grid; grid-template-columns: 1fr 1fr; border-top: 1px solid #333; }}
        .quadrant {{ padding: 15px; border-right: 1px solid #333; border-bottom: 1px solid #333; }}
        .quadrant:nth-child(2n) {{ border-right: none; }}
        .q-title {{ font-size: 0.75em; color: #888; text-transform: uppercase; margin-bottom: 5px; letter-spacing: 1px; }}
        .q-data {{ font-size: 0.95em; font-weight: bold; }}
        .sub-data {{ font-size: 0.8em; color: #aaa; display: block; margin-top: 2px; }}
        
        /* Risk/Reward Bar */
        .rr-sec {{ padding: 15px; }}
        .rr-bar-bg {{ height: 6px; background: #333; border-radius: 3px; position: relative; margin: 10px 0; }}
        .rr-fill {{ width: 50%; height: 100%; background: #666; position: absolute; left: 0; }} 
        /* 這裡用簡單的視覺表示風報比，或是支撐壓力位置 */
        
        /* Signals List */
        .signals-sec {{ padding: 10px 15px; background: rgba(255,255,255,0.03); }}
        .signal-tag {{ display: inline-block; font-size: 0.8em; background: #333; padding: 3px 8px; border-radius: 4px; margin-right: 5px; margin-bottom: 5px; border: 1px solid #444; }}
        
        /* Fundamental & News */
        .fund-sec {{ padding: 15px; font-size: 0.9em; color: #ccc; border-top: 1px solid #333; }}
        .news-item {{ margin-bottom: 8px; padding-bottom: 8px; border-bottom: 1px solid #222; }}
        .news-item:last-child {{ border: none; }}
        
        .footer {{ text-align: center; font-size: 0.8em; color: #666; margin-top: 30px; }}
    </style>
</head>
<body>

    <div class="macro-header">
        <div style="font-size: 0.9em; color: #aaa;">MARKET CLIMATE SCORE</div>
        <div class="macro-score">{macro['Score']}</div>
        <div class="macro-trend">{macro['Trend']}</div>
        <br>
        <div class="macro-list">
            {''.join([f'• {d}<br>' for d in macro['Details']])}
        </div>
    </div>

    """

for s in results:
    c = "up" if s['change'] >= 0 else "down"
    sign = "+" if s['change'] >= 0 else ""
    
    html += f"""
    <div class="report-card">
        <div class="card-header">
            <div class="stock-title">
                <h1>{s['name']}</h1>
                <span>{s['id']}</span>
            </div>
            <div class="verdict-badge" style="background: {s['verdict_color']};">{s['verdict']}</div>
        </div>
        
        <div class="price-sec">
            <div class="big-price">${s['price']}</div>
            <div class="price-change {c}">{sign}{s['change']}%</div>
        </div>
        
        <div class="analysis-grid">
            <div class="quadrant">
                <div class="q-title">相對強度 (RS)</div>
                <div class="q-data" style="color: {'#ff4d4d' if s['chips']['rs_val']>0 else '#00b894'}">{s['chips']['rs_val']}%</div>
                <span class="sub-data">{s['chips']['status']}</span>
            </div>
            <div class="quadrant">
                <div class="q-title">技術指標</div>
                <div class="q-data">RSI: {s['tech']['rsi']}</div>
                <span class="sub-data">均線{s['tech']['ma_align']} | 布林{s['tech']['bb_pos']}</span>
            </div>
            <div class="quadrant">
                <div class="q-title">風報比 (R/R)</div>
                <div class="q-data">{s['rr']['ratio']}</div>
                <span class="sub-data">上檔 {s['rr']['upside']}% | 下檔 {s['rr']['downside']}%</span>
            </div>
            <div class="quadrant">
                <div class="q-title">基本面</div>
                <div class="q-data">PE: {s['fund']['PE']}</div>
                <span class="sub-data">營收成長: {round(s['fund']['RevGrowth']*100, 1) if s['fund']['RevGrowth'] else '-'}%</span>
            </div>
        </div>
        
        <div class="signals-sec">
            {''.join([f'<span class="signal-tag">{sig}</span>' for sig in s['signals']])}
        </div>
        
        <div class="fund-sec">
            <div style="color: #bb86fc; font-weight: bold; margin-bottom: 10px;">📰 重大消息追蹤</div>
            {''.join([f'<div class="news-item">{n}</div>' for n in s['news']])}
        </div>
    </div>
    """

html += f"""
    <div class="footer">
        Generated by AI Pro Analyst • {APP_VERSION}<br>
        Data source: Yahoo Finance / TWSE
    </div>
</body>
</html>
"""

with open("index.html", "w", encoding="utf-8") as f:
    f.write(html)
