import yfinance as yf
import pandas as pd
import requests
from bs4 import BeautifulSoup
import ta
import datetime
import time
import twstock

# 🟢 版本號
APP_VERSION = "v6.0 (大盤+頁碼版)"

def get_market_status():
    """
    🌍 獲取大盤指數 (台股、美股費半、那斯達克、標普)
    """
    print("🌍 正在分析全球大盤趨勢...")
    indices = {
        "台股加權": "^TWII",
        "費城半導體": "^SOX",  # 影響台積電最深
        "那斯達克": "^IXIC",   # 科技股風向
        "S&P 500": "^GSPC"    # 美股整體
    }
    
    market_data = []
    try:
        for name, code in indices.items():
            # 抓取資料
            df = yf.download(code, period="5d", progress=False)
            if len(df) >= 2:
                # 處理 MultiIndex
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                    
                today = df.iloc[-1]
                prev = df.iloc[-2]
                price = round(today['Close'], 2)
                change_pct = round((today['Close'] - prev['Close']) / prev['Close'] * 100, 2)
                
                # 判斷趨勢 (簡單用 MA5)
                ma5 = df['Close'].tail(5).mean()
                trend = "偏多" if price > ma5 else "偏空"
                
                market_data.append({
                    "name": name,
                    "price": price,
                    "change": change_pct,
                    "trend": trend
                })
    except Exception as e:
        print(f"大盤資料錯誤: {e}")
        
    return market_data

def get_volume_leaders():
    """爬取 Yahoo 股市人氣排行榜 (前 150 名)"""
    print("🕷️ 正在爬取 Yahoo 股市人氣排行榜...")
    leaders = []
    try:
        urls = [
            "https://tw.stock.yahoo.com/rank/turnover?exchange=TAI", 
            "https://tw.stock.yahoo.com/rank/turnover?exchange=TWO"
        ]
        headers = {'User-Agent': 'Mozilla/5.0'}

        for url in urls:
            response = requests.get(url, headers=headers)
            soup = BeautifulSoup(response.text, 'html.parser')
            links = soup.find_all('a', href=True)
            for link in links:
                href = link['href']
                if "/quote/" in href and (".TW" in href or ".TWO" in href):
                    ticker = href.split("/quote/")[-1]
                    if ticker not in leaders:
                        leaders.append(ticker)
            time.sleep(1)
        return leaders[:150] 
    except:
        return ['2330.TW']

def get_stock_info(ticker):
    """取得股票名稱與產業"""
    try:
        code = ticker.split('.')[0]
        if code in twstock.codes:
            info = twstock.codes[code]
            return info.name, info.group
    except:
        pass
    return ticker, "一般產業"

def get_news_and_growth(ticker):
    """挖掘未來性：爬取最新新聞標題 + 成長率數據"""
    news_list = []
    growth_data = {"Rev_Growth": "N/A", "PEG": "N/A", "Outlook": "平穩"}
    
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        rev_growth = info.get('revenueGrowth', None)
        if rev_growth:
            growth_data['Rev_Growth'] = f"{round(rev_growth * 100, 1)}%"
            if rev_growth > 0.3: growth_data['Outlook'] = "🔥 高速成長"
            elif rev_growth > 0.1: growth_data['Outlook'] = "📈 穩定擴張"
            elif rev_growth < -0.1: growth_data['Outlook'] = "📉 營收衰退"
            
        peg = info.get('pegRatio', None)
        if peg: growth_data['PEG'] = str(peg)
            
        # 爬蟲
        headers = {'User-Agent': 'Mozilla/5.0'}
        news_url = f"https://tw.stock.yahoo.com/quote/{ticker}/news"
        r = requests.get(news_url, headers=headers)
        soup = BeautifulSoup(r.text, 'html.parser')
        titles = soup.find_all('h3', limit=5)
        for t in titles:
            link = t.find('a')
            if link and link.text and len(link.text) > 10:
                news_list.append(link.text)
        
        if not news_list: news_list = ["尚無即時重大新聞"]
    except:
        news_list = ["無法取得新聞"]
        
    return news_list[:3], growth_data

def get_fundamentals(ticker):
    """查詢基本面"""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        pe = info.get('trailingPE', None)
        eps = info.get('trailingEps', None)
        roe = info.get('returnOnEquity', None)
        yield_rate = info.get('dividendYield', None)
        
        data = {
            "PE": f"{round(pe, 1)}倍" if pe else "N/A",
            "EPS": f"${round(eps, 2)}" if eps else "N/A",
            "ROE": f"{round(roe * 100, 1)}%" if roe else "N/A",
            "Yield": f"{round(yield_rate * 100, 1)}%" if yield_rate else "N/A",
            "Score": "中性"
        }
        
        good_points = 0
        if pe and 0 < pe < 15: good_points += 1
        if eps and eps > 0: good_points += 1
        if roe and roe > 0.1: good_points += 1
        if yield_rate and yield_rate > 0.04: good_points += 1
        
        if good_points >= 3: data["Score"] = "💎 體質優良"
        elif good_points >= 2: data["Score"] = "👌 體質尚可"
        elif eps and eps < 0: data["Score"] = "⚠️ 虧損中"
        else: data["Score"] = "😐 普通"
        return data
    except:
        return {"PE": "-", "EPS": "-", "ROE": "-", "Yield": "-", "Score": "無資料"}

def analyze_stock(ticker):
    try:
        df = yf.download(ticker, period="3mo", progress=False)
        if df.empty or len(df) < 20: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)

        df['MA5'] = df['Close'].rolling(window=5).mean()
        df['MA20'] = df['Close'].rolling(window=20).mean()
        df['Vol_MA5'] = df['Volume'].rolling(window=5).mean()
        df['RSI'] = ta.momentum.RSIIndicator(close=df['Close'], window=14).rsi()
        
        today = df.iloc[-1]
        yesterday = df.iloc[-2]
        price = round(float(today['Close']), 2)
        rsi = round(float(today['RSI']), 1)
        change = round((today['Close'] - yesterday['Close']) / yesterday['Close'] * 100, 2)
        
        if rsi > 75: return None 

        signal_type = None
        reasons = []
        
        if yesterday['MA5'] < yesterday['MA20'] and today['MA5'] > today['MA20']:
            reasons.append("MA5 黃金交叉")
        if today['Volume'] > today['Vol_MA5'] * 1.5:
            reasons.append(f"爆量 ({round(today['Volume']/today['Vol_MA5'], 1)}倍)")
        if today['Close'] > today['MA20']:
            reasons.append("站上月線")

        if "黃金交叉" in str(reasons) or "爆量" in str(reasons):
            signal_type = "✨ 值得關注"
            if "爆量" in str(reasons) and "黃金交叉" in str(reasons):
                signal_type = "🔥 強力買進訊號"
        
        if signal_type:
            name, industry = get_stock_info(ticker)
            fund_data = get_fundamentals(ticker)
            news, growth = get_news_and_growth(ticker)
            
            return {
                "id": ticker, "name": name, "industry": industry,
                "price": price, "change": change, "rsi": rsi,
                "signal": signal_type, "reasons": reasons,
                "fund": fund_data, "news": news, "growth": growth
            }
        return None
    except:
        return None

# === 1. 先抓大盤資料 ===
market_status = get_market_status()

# === 2. 執行個股分析 ===
stock_list = get_volume_leaders()
results = []
print(f"開始掃描 {len(stock_list)} 檔股票...")

for i, stock in enumerate(stock_list):
    if i % 10 == 0: print(f"進度: {i}...")
    res = analyze_stock(stock)
    if res:
        results.append(res)

results.sort(key=lambda x: (x['signal'] != "🔥 強力買進訊號", x['rsi']))

# === 3. 產出 HTML ===
html_content = f"""
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>AI Stock {APP_VERSION}</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ background-color: #000; color: #fff; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; overflow: hidden; }}
        .snap-container {{ height: 100vh; width: 100vw; overflow-y: scroll; scroll-snap-type: y mandatory; scroll-behavior: smooth; }}
        .stock-card {{ height: 100vh; width: 100vw; scroll-snap-align: start; padding: 15px; display: flex; flex-direction: column; background: linear-gradient(180deg, #121212 0%, #000000 100%); border-bottom: 1px solid #333; position: relative; }}
        
        /* 大盤儀表板樣式 */
        .dashboard-card {{ background: linear-gradient(180deg, #1a2a6c 0%, #b21f1f 100%); align-items: center; justify-content: center; }}
        .market-title {{ font-size: 2em; font-weight: bold; margin-bottom: 20px; }}
        .market-grid {{ width: 100%; max-width: 400px; display: grid; grid-template-columns: 1fr 1fr; gap: 15px; }}
        .market-item {{ background: rgba(255,255,255,0.1); padding: 15px; border-radius: 10px; text-align: center; }}
        .market-name {{ font-size: 0.9em; color: #ddd; }}
        .market-change {{ font-size: 1.4em; font-weight: bold; margin-top: 5px; }}
        
        /* 個股樣式 */
        .top-row {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px; }}
        .stock-info h1 {{ font-size: 2em; margin-bottom: 2px; }}
        .stock-info h2 {{ font-size: 1em; color: #888; font-weight: normal; }}
        .industry-tag {{ background: #333; padding: 4px 8px; border-radius: 10px; font-size: 0.7em; color: #ddd; height: fit-content; }}
        
        /* 頁碼標示 */
        .page-counter {{ position: absolute; top: 15px; right: 15px; background: rgba(255,255,255,0.2); padding: 3px 8px; border-radius: 10px; font-size: 0.8em; color: #fff; }}

        .price-section {{ margin-bottom: 15px; display: flex; align-items: baseline; }}
        .big-price {{ font-size: 3em; font-weight: 800; }}
        .change-percent {{ font-size: 1.2em; font-weight: bold; margin-left: 10px; }}
        .up {{ color: #ff4d4d; }} .down {{ color: #00b894; }}
        .growth-badge {{ background: #2c3e50; color: #ecf0f1; padding: 3px 8px; border-radius: 4px; font-size: 0.8em; margin-left: 10px; border: 1px solid #34495e; }}

        .fund-grid {{ display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 5px; margin-bottom: 15px; background: rgba(255,255,255,0.05); padding: 10px; border-radius: 12px; }}
        .fund-item {{ display: flex; flex-direction: column; text-align: center; }}
        .fund-label {{ font-size: 0.7em; color: #aaa; }}
        .fund-val {{ font-size: 0.9em; font-weight: bold; color: #fff; }}
        
        .news-box {{ flex-grow: 1; background: rgba(255,255,255,0.03); padding: 15px; border-radius: 12px; overflow-y: auto; margin-bottom: 30px; }}
        .news-title {{ font-size: 0.9em; color: #f39c12; margin-bottom: 10px; font-weight: bold; }}
        .news-list {{ list-style: none; }}
        .news-list li {{ font-size: 0.95em; margin-bottom: 12px; line-height: 1.4; color: #ddd; border-bottom: 1px solid #333; padding-bottom: 8px; }}
        
        .signal-box {{ background: rgba(52, 152, 219, 0.15); padding: 10px; border-radius: 8px; border-left: 3px solid #3498db; margin-bottom: 10px; }}
        .signal-header {{ font-weight: bold; color: #3498db; font-size: 1em; }}
        
        .footer {{ position: absolute; bottom: 15px; width: 100%; text-align: center; color: #444; font-size: 0.7em; left:0; }}
    </style>
</head>
<body>
    <div class="snap-container">
"""

# === 第一張卡片：大盤儀表板 ===
html_content += f"""
        <div class="stock-card dashboard-card">
            <div class="market-title">🌍 全球大盤趨勢</div>
            <div class="market-grid">
"""
for m in market_status:
    m_color = "up" if m['change'] >= 0 else "down"
    m_sign = "+" if m['change'] >= 0 else ""
    html_content += f"""
                <div class="market-item">
                    <div class="market-name">{m['name']}</div>
                    <div class="market-change {m_color}">{m_sign}{m['change']}%</div>
                    <div style="font-size:0.8em; margin-top:5px; color:#aaa;">{m['trend']}</div>
                </div>
    """
html_content += """
            </div>
            <div style="margin-top: 30px; color: #ddd; font-size: 0.9em;">
                觀察重點：<br>
                1. 費半跌重，小心台積電<br>
                2. 美股若大跌，台股開盤易開低
            </div>
            <div class="footer">往上滑動開始選股 ▲</div>
        </div>
"""

# === 後續卡片：個股分析 ===
total_stocks = len(results)

if not results:
    html_content += """
        <div class="stock-card" style="text-align: center; justify-content: center;">
            <h1 style="color: #666">😴 今日無訊號</h1>
            <p style="color: #444; margin-top: 10px">大盤可能不佳，建議空手觀望</p>
        </div>
    """
else:
    for i, item in enumerate(results):
        c_color = "up" if item['change'] >= 0 else "down"
        sign = "+" if item['change'] >= 0 else ""
        outlook_color = "#e74c3c" if "成長" in item['growth']['Outlook'] else "#7f8c8d"
        
        # 🟢 頁碼 (因為第一頁是大盤，所以這裡顯示 第 X / Y 檔)
        counter_str = f"{i+1} / {total_stocks}"
        
        html_content += f"""
        <div class="stock-card">
            <div class="page-counter">{counter_str}</div>
            
            <div class="top-row">
                <div class="stock-info">
                    <h1>{item['name']}</h1>
                    <h2>{item['id']} <span style="font-size:0.6em; color:{outlook_color}; border:1px solid {outlook_color}; padding:2px 5px; border-radius:4px; margin-left:5px;">{item['growth']['Outlook']}</span></h2>
                </div>
                <div class="industry-tag">{item['industry']}</div>
            </div>
            
            <div class="price-section">
                <span class="big-price">${item['price']}</span>
                <span class="change-percent {c_color}">{sign}{item['change']}%</span>
                <span class="growth-badge">營收年增: {item['growth']['Rev_Growth']}</span>
            </div>
            
            <div class="signal-box">
                <div class="signal-header">{item['signal']}</div>
            </div>

            <div class="fund-grid">
                <div class="fund-item"><span class="fund-label">PE</span><span class="fund-val">{item['fund']['PE']}</span></div>
                <div class="fund-item"><span class="fund-label">EPS</span><span class="fund-val">{item['fund']['EPS']}</span></div>
                <div class="fund-item"><span class="fund-label">殖利</span><span class="fund-val">{item['fund']['Yield']}</span></div>
                <div class="fund-item"><span class="fund-label">評分</span><span class="fund-val" style="color:#f1c40f">{item['fund']['Score']}</span></div>
            </div>
            
            <div class="news-box">
                <div class="news-title">
                    <span>📰 市場消息與產業前景</span>
                </div>
                <ul class="news-list">
                    {''.join([f"<li>{news}</li>" for news in item['news']])}
                </ul>
            </div>
            
            <div class="footer">RSI: {item['rsi']} | {APP_VERSION}</div>
        </div>
        """

html_content += "</div></body></html>"

with open("index.html", "w", encoding="utf-8") as f:
    f.write(html_content)
