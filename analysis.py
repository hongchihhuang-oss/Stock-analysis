import yfinance as yf
import pandas as pd
import requests
import ta
import datetime
import time
import twstock
from bs4 import BeautifulSoup

# 🟢 版本號
APP_VERSION = "v10.0 (全功能旗艦版)"

# ==========================================
# 1. 大盤儀表板 (保留穩定版)
# ==========================================
def get_market_status():
    print("🌍 正在分析大盤趨勢...")
    status = {"Trend": "盤整", "Color": "#f39c12", "Details": "數據讀取中"}
    try:
        data = yf.download(["^TWII", "^SOX"], period="1mo", progress=False)['Close']
        twii_now = data['^TWII'].iloc[-1]
        twii_ma20 = data['^TWII'].tail(20).mean()
        sox_now = data['^SOX'].iloc[-1]
        sox_prev = data['^SOX'].iloc[-2]
        
        is_bullish = twii_now > twii_ma20
        sox_up = sox_now > sox_prev
        
        if is_bullish and sox_up:
            status = {"Trend": "🚀 多頭助攻", "Color": "#ff4d4d", "Details": "台股站穩月線 + 美股半導體上漲"}
        elif is_bullish:
            status = {"Trend": "📈 偏多震盪", "Color": "#e74c3c", "Details": "台股趨勢向上，留意美股波動"}
        elif not is_bullish and not sox_up:
            status = {"Trend": "📉 空頭修正", "Color": "#00b894", "Details": "台股跌破月線 + 費半走弱"}
        else:
            status = {"Trend": "⚠️ 弱勢盤整", "Color": "#f39c12", "Details": "台股技術面轉弱，建議觀望"}
            
        status['TWII_Price'] = int(twii_now)
        status['SOX_Change'] = round((sox_now - sox_prev) / sox_prev * 100, 2)
    except:
        status = {"Trend": "資料連線失敗", "Color": "#777", "Details": "無法取得行情"}
    return status

# ==========================================
# 2. 資料獲取與爬蟲
# ==========================================
def get_volume_leaders():
    """抓取熱門股前 15 檔"""
    print("🕷️ 正在爬取熱門排行...")
    leaders = []
    try:
        urls = ["https://tw.stock.yahoo.com/rank/turnover?exchange=TAI"]
        headers = {'User-Agent': 'Mozilla/5.0'}
        for url in urls:
            r = requests.get(url, headers=headers)
            soup = BeautifulSoup(r.text, 'html.parser')
            links = soup.find_all('a', href=True)
            for link in links:
                href = link['href']
                if "/quote/" in href and ".TW" in href:
                    ticker = href.split("/quote/")[-1]
                    if ticker not in leaders: 
                        leaders.append(ticker)
                        if len(leaders) >= 12: break 
        return leaders
    except: return ['2330.TW', '2317.TW', '2603.TW', '2454.TW']

def get_stock_info(ticker):
    try:
        code = ticker.split('.')[0]
        if code in twstock.codes:
            info = twstock.codes[code]
            return info.name, info.group
    except: pass
    return ticker, "熱門股"

def get_news(ticker):
    news_list = []
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(f"https://tw.stock.yahoo.com/quote/{ticker}/news", headers=headers)
        soup = BeautifulSoup(r.text, 'html.parser')
        titles = soup.find_all('h3', limit=3)
        for t in titles:
            link = t.find('a')
            if link and link.text: news_list.append(link.text)
    except: news_list = ["尚無新聞"]
    return news_list if news_list else ["無重大新聞"]

def get_advanced_data(ticker):
    """
    🔍 獲取進階數據：法人目標價、基本面、建議
    """
    data = {"Target": "N/A", "PE": "-", "EPS": "-", "ROE": "-", "Rec": "中性"}
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        # 嘗試抓取目標價 (有些台股可能有)
        tgt = info.get('targetMeanPrice')
        if tgt: data["Target"] = f"${tgt}"
        
        # 基本面
        pe = info.get('trailingPE')
        eps = info.get('trailingEps')
        roe = info.get('returnOnEquity')
        rec = info.get('recommendationKey')
        
        if pe: data["PE"] = f"{round(pe, 1)}倍"
        if eps: data["EPS"] = f"${round(eps, 2)}"
        if roe: data["ROE"] = f"{round(roe*100, 1)}%"
        
        # 翻譯建議
        rec_map = {"buy": "買進", "strong_buy": "強力買進", "hold": "持有", "sell": "賣出"}
        if rec and rec in rec_map: data["Rec"] = rec_map[rec]
        
    except: pass
    return data

# ==========================================
# 3. 核心分析邏輯
# ==========================================
def analyze_stock(ticker):
    try:
        # 抓取較長天期以計算壓力支撐
        df = yf.download(ticker, period="6mo", progress=False)
        if df.empty or len(df) < 60: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)

        # === 技術指標 ===
        close = df['Close']
        df['MA5'] = close.rolling(5).mean()
        df['MA20'] = close.rolling(20).mean()
        df['MA60'] = close.rolling(60).mean()
        df['Vol_MA5'] = df['Volume'].rolling(5).mean()
        
        # KD
        stoch = ta.momentum.StochasticOscillator(df['High'], df['Low'], close)
        df['K'] = stoch.stoch()
        
        # MACD
        macd = ta.trend.MACD(close)
        df['MACD_Hist'] = macd.macd_diff()

        # === 壓力與支撐 (視覺化關鍵) ===
        # 抓最近 60 天的最高與最低價
        recent_high = df['High'].tail(60).max()
        recent_low = df['Low'].tail(60).min()
        
        today = df.iloc[-1]
        prev = df.iloc[-2]
        price = round(float(today['Close']), 2)
        change = round((today['Close'] - prev['Close']) / prev['Close'] * 100, 2)
        k_val = round(float(today['K']), 1)
        
        # === 訊號判定 ===
        signal = "👀 持續觀察"
        signal_color = "#95a5a6" # 灰
        tags = [] # 小標籤
        
        # 1. 均線邏輯
        if price > today['MA20'] and price > today['MA60']:
            tags.append("多頭排列")
        elif price < today['MA20']:
            tags.append("跌破月線")
            
        # 2. 動能邏輯
        if today['Volume'] > today['Vol_MA5'] * 1.5:
            tags.append("爆量")
        
        if prev['MA5'] < prev['MA20'] and today['MA5'] > today['MA20']:
            tags.append("黃金交叉")
            signal = "✨ 轉強訊號"
            signal_color = "#f39c12" # 橘

        # 3. 籌碼/主力模擬
        is_strong = False
        if "爆量" in tags and "黃金交叉" in tags:
            signal = "🔥 強力買進"
            signal_color = "#ff4d4d" # 紅
            is_strong = True
        
        # 取得額外資訊
        name, industry = get_stock_info(ticker)
        adv_data = get_advanced_data(ticker)
        news = get_news(ticker)
        
        # 計算目前價格在壓力支撐的位置 (0-100%)
        pos_pct = 50
        if recent_high != recent_low:
            pos_pct = (price - recent_low) / (recent_high - recent_low) * 100
            pos_pct = max(0, min(100, pos_pct))

        return {
            "id": ticker, "name": name, "industry": industry,
            "price": price, "change": change, 
            "k": k_val, "macd_hist": round(today['MACD_Hist'], 2),
            "support": round(recent_low, 2), "pressure": round(recent_high, 2), "pos_pct": pos_pct,
            "signal": signal, "signal_color": signal_color, "tags": tags,
            "adv": adv_data, "news": news
        }
    except Exception as e:
        print(f"Error {ticker}: {e}")
        return None

# === 執行掃描 ===
market = get_market_status()
stock_list = get_volume_leaders()
results = []

print(f"開始分析 {len(stock_list)} 檔股票...")
for stock in stock_list:
    res = analyze_stock(stock)
    if res: results.append(res)

# 排序: 強力買進 > 轉強 > 觀察
results.sort(key=lambda x: (x['signal'] == "👀 持續觀察", x['change']), reverse=True)

# === HTML 產出 (Restore v8.0 UI) ===
html_content = f"""
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Pro Stock {APP_VERSION}</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ background-color: #0b0e11; color: #e1e1e1; font-family: -apple-system, Roboto, sans-serif; overflow: hidden; }}
        .snap-container {{ height: 100vh; width: 100vw; overflow-y: scroll; scroll-snap-type: y mandatory; }}
        .stock-card {{ height: 100vh; width: 100vw; scroll-snap-align: start; padding: 15px; display: flex; flex-direction: column; background: #0b0e11; border-bottom: 1px solid #222; position: relative; }}
        
        /* Dashboard */
        .dashboard {{ background: linear-gradient(135deg, #1e2a78 0%, #ff5e62 100%); justify-content: center; align-items: center; text-align: center; }}
        .mkt-status {{ font-size: 2.5em; font-weight: bold; margin: 20px 0; }}
        
        /* Stock Header */
        .top-row {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 5px; }}
        .stock-name {{ font-size: 2em; font-weight: 800; margin: 0; }}
        .stock-id {{ color: #888; font-size: 1em; }}
        .tag-ind {{ background: #222; padding: 4px 10px; border-radius: 10px; font-size: 0.8em; }}
        
        /* Price */
        .price-row {{ display: flex; align-items: baseline; margin-bottom: 15px; }}
        .price {{ font-size: 3em; font-weight: 800; }}
        .change {{ font-size: 1.3em; font-weight: bold; margin-left: 15px; }}
        .up {{ color: #ff4d4d; }} .down {{ color: #00b894; }}
        
        /* 壓力支撐條 (Visual Bar) */
        .range-box {{ margin-bottom: 20px; }}
        .range-bar {{ height: 8px; background: #333; border-radius: 4px; position: relative; margin: 5px 0; }}
        .range-fill {{ height: 100%; background: linear-gradient(90deg, #00b894, #ff4d4d); opacity: 0.5; border-radius: 4px; }}
        .range-cursor {{ position: absolute; top: -4px; width: 4px; height: 16px; background: #fff; box-shadow: 0 0 5px white; border-radius: 2px; }}
        .range-label {{ display: flex; justify-content: space-between; font-size: 0.75em; color: #888; }}
        
        /* Grid Data */
        .grid-box {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; margin-bottom: 15px; }}
        .grid-item {{ background: rgba(255,255,255,0.05); padding: 8px; border-radius: 8px; text-align: center; }}
        .lbl {{ font-size: 0.7em; color: #aaa; display: block; }}
        .val {{ font-size: 0.9em; font-weight: bold; }}
        
        /* Signal & Tags */
        .signal-box {{ padding: 10px; border-radius: 8px; margin-bottom: 15px; font-weight: bold; border-left: 4px solid; display: flex; justify-content: space-between; align-items: center; }}
        .tags {{ display: flex; gap: 5px; }}
        .tag {{ font-size: 0.7em; background: rgba(0,0,0,0.3); padding: 2px 6px; border-radius: 4px; }}
        
        /* News */
        .news-area {{ flex-grow: 1; overflow-y: auto; font-size: 0.9em; color: #bbb; }}
        .news-area li {{ margin-bottom: 8px; border-bottom: 1px solid #222; padding-bottom: 4px; }}
        
        .footer {{ position: absolute; bottom: 10px; width: 100%; text-align: center; color: #444; font-size: 0.7em; left: 0; }}
        .pg-num {{ position: absolute; top: 20px; right: 20px; background: #333; padding: 2px 8px; border-radius: 10px; font-size: 0.8em; }}
    </style>
</head>
<body>
    <div class="snap-container">
        <div class="stock-card dashboard">
            <h2 style="color:rgba(255,255,255,0.8)">🌍 全球趨勢</h2>
            <div class="mkt-status" style="color: {market['Color']}">{market['Trend']}</div>
            <p style="background:rgba(0,0,0,0.2); padding:15px; border-radius:10px;">
                {market['Details']}<br>
                <span style="font-size:0.8em; color:#ccc">TWII: {market.get('TWII_Price',0)}</span>
            </p>
            <div style="margin-top:20px; font-size:0.9em; animation: bounce 1.5s infinite;">往上滑動看熱門股 ▲</div>
        </div>
"""

for i, item in enumerate(results):
    c = "up" if item['change'] >= 0 else "down"
    sign = "+" if item['change'] >= 0 else ""
    
    html_content += f"""
        <div class="stock-card">
            <div class="pg-num">{i+1} / {len(results)}</div>
            
            <div class="top-row">
                <div>
                    <h1 class="stock-name">{item['name']}</h1>
                    <span class="stock-id">{item['id']}</span>
                </div>
                <div class="tag-ind">{item['industry']}</div>
            </div>
            
            <div class="price-row">
                <span class="price">${item['price']}</span>
                <span class="change {c}">{sign}{item['change']}%</span>
            </div>
            
            <div class="range-box">
                <div class="range-bar">
                    <div class="range-fill" style="width: 100%"></div>
                    <div class="range-cursor" style="left: {item['pos_pct']}%"></div>
                </div>
                <div class="range-label">
                    <span>支撐 ${item['support']}</span>
                    <span>壓力 ${item['pressure']}</span>
                </div>
            </div>
            
            <div class="signal-box" style="background: {item['signal_color']}20; border-color: {item['signal_color']}; color: {item['signal_color']}">
                <span>{item['signal']}</span>
                <div class="tags">
                    {''.join([f'<span class="tag">{t}</span>' for t in item['tags']])}
                </div>
            </div>
            
            <div class="grid-box">
                <div class="grid-item">
                    <span class="lbl">KD(9,3)</span>
                    <span class="val">K: {item['k']}</span>
                </div>
                <div class="grid-item">
                    <span class="lbl">本益比</span>
                    <span class="val">{item['adv']['PE']}</span>
                </div>
                <div class="grid-item">
                    <span class="lbl">EPS</span>
                    <span class="val">{item['adv']['EPS']}</span>
                </div>
                <div class="grid-item">
                    <span class="lbl">法人目標</span>
                    <span class="val" style="color:#f1c40f">{item['adv']['Target']}</span>
                </div>
                <div class="grid-item">
                    <span class="lbl">分析建議</span>
                    <span class="val">{item['adv']['Rec']}</span>
                </div>
                <div class="grid-item">
                    <span class="lbl">ROE</span>
                    <span class="val">{item['adv']['ROE']}</span>
                </div>
            </div>
            
            <div class="news-area">
                <div style="color:#f39c12; font-weight:bold; margin-bottom:5px;">📰 重點新聞</div>
                <ul style="padding-left:0; list-style:none;">
                    {''.join([f"<li>{n}</li>" for n in item['news']])}
                </ul>
            </div>
            
            <div class="footer">{APP_VERSION}</div>
        </div>
    """

html_content += "</div></body></html>"

with open("index.html", "w", encoding="utf-8") as f:
    f.write(html_content)
