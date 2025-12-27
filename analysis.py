import yfinance as yf
import pandas as pd
import requests
from bs4 import BeautifulSoup
import ta
import datetime
import time
import twstock # 用來查產業類別

def get_volume_leaders():
    """
    爬取 Yahoo 股市人氣排行榜
    """
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
        return leaders[:150] # 掃描前 150 檔
    except Exception as e:
        print(f"❌ 爬蟲錯誤: {e}")
        return ['2330.TW', '2317.TW']

def get_stock_info(ticker):
    """
    取得股票名稱與產業類別 (利用 twstock)
    """
    try:
        code = ticker.split('.')[0] # 去掉 .TW
        if code in twstock.codes:
            info = twstock.codes[code]
            return info.name, info.group # 回傳 (名稱, 產業)
    except:
        pass
    return ticker, "一般產業"

def analyze_stock(ticker):
    try:
        df = yf.download(ticker, period="3mo", progress=False)
        if df.empty or len(df) < 20: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)

        # 計算指標
        df['MA5'] = df['Close'].rolling(window=5).mean()
        df['MA20'] = df['Close'].rolling(window=20).mean()
        df['Vol_MA5'] = df['Volume'].rolling(window=5).mean()
        rsi_indicator = ta.momentum.RSIIndicator(close=df['Close'], window=14)
        df['RSI'] = rsi_indicator.rsi()
        
        today = df.iloc[-1]
        yesterday = df.iloc[-2]
        
        # 取得目前數據
        price = round(float(today['Close']), 2)
        rsi = round(float(today['RSI']), 1)
        change = round((today['Close'] - yesterday['Close']) / yesterday['Close'] * 100, 2)
        
        # 🛡️ 過熱保護
        if rsi > 75: return None 

        # 訊號判斷
        signal_type = None
        reasons = []
        
        if yesterday['MA5'] < yesterday['MA20'] and today['MA5'] > today['MA20']:
            reasons.append("MA5 穿過 MA20 黃金交叉")
            
        if today['Volume'] > today['Vol_MA5'] * 1.5:
            reasons.append(f"成交量爆增 (是 5日均量的 {round(today['Volume']/today['Vol_MA5'], 1)} 倍)")
            
        if today['Close'] > today['MA20']:
            reasons.append("股價站穩月線之上")

        # 綜合篩選
        if "黃金交叉" in str(reasons) or ("成交量爆增" in str(reasons) and price > today['MA20']):
            signal_type = "✨ 值得關注"
            if "成交量爆增" in str(reasons) and "黃金交叉" in str(reasons):
                signal_type = "🔥 強力買進訊號"
        
        if signal_type:
            name, industry = get_stock_info(ticker)
            return {
                "id": ticker,
                "name": name,
                "industry": industry,
                "price": price,
                "change": change,
                "rsi": rsi,
                "signal": signal_type,
                "reasons": reasons
            }
        return None
    except:
        return None

# === 執行分析 ===
stock_list = get_volume_leaders()
results = []
print(f"開始掃描 {len(stock_list)} 檔股票...")

for i, stock in enumerate(stock_list):
    res = analyze_stock(stock)
    if res:
        results.append(res)

# 排序
results.sort(key=lambda x: (x['signal'] != "🔥 強力買進訊號", x['rsi']))

# === 產出 APP 風格 HTML ===
html_content = f"""
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>AI Stock Swipe</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ 
            background-color: #000; 
            color: #fff; 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            overflow: hidden; /* 禁止網頁整體滾動 */
        }}
        
        /* 核心：單頁滑動容器 */
        .snap-container {{
            height: 100vh;
            width: 100vw;
            overflow-y: scroll;
            scroll-snap-type: y mandatory;
            scroll-behavior: smooth;
        }}

        /* 每一張卡片 */
        .stock-card {{
            height: 100vh;
            width: 100vw;
            scroll-snap-align: start;
            display: flex;
            flex-direction: column;
            justify-content: center;
            padding: 30px;
            position: relative;
            background: linear-gradient(180deg, #1a1a1a 0%, #000000 100%);
            border-bottom: 1px solid #333;
        }}

        /* 產業標籤 */
        .industry-badge {{
            position: absolute;
            top: 40px;
            right: 30px;
            background: rgba(255, 255, 255, 0.2);
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 0.9em;
            backdrop-filter: blur(5px);
        }}

        /* 股票代號與名稱 */
        .stock-header h1 {{ font-size: 2.5em; margin-bottom: 5px; }}
        .stock-header h2 {{ font-size: 1.2em; color: #aaa; font-weight: normal; margin-bottom: 20px; }}

        /* 股價 */
        .price-box {{ margin-bottom: 30px; }}
        .price {{ font-size: 3.5em; font-weight: 800; letter-spacing: -1px; }}
        .change {{ font-size: 1.2em; font-weight: bold; margin-left: 10px; }}
        .up {{ color: #ff4d4d; }} /* 台股漲是紅色 */
        .down {{ color: #00b894; }}

        /* 訊號與理由 */
        .signal-box {{ 
            background: rgba(255,255,255,0.1); 
            padding: 20px; 
            border-radius: 16px; 
            backdrop-filter: blur(10px);
        }}
        .signal-title {{ 
            font-size: 1.2em; 
            font-weight: bold; 
            margin-bottom: 15px; 
            color: #f1c40f; 
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        .reason-list {{ list-style: none; }}
        .reason-list li {{ 
            margin-bottom: 10px; 
            padding-left: 20px; 
            position: relative; 
            font-size: 1.1em;
            line-height: 1.4;
        }}
        .reason-list li::before {{
            content: "✔";
            color: #00b894;
            position: absolute;
            left: 0;
            top: 2px;
        }}

        /* 底部資訊 */
        .footer-info {{
            position: absolute;
            bottom: 40px;
            left: 30px;
            right: 30px;
            display: flex;
            justify-content: space-between;
            color: #666;
            font-size: 0.9em;
        }}
        
        .rsi-val {{ color: #aaa; }}

        /* 提示滑動 */
        .swipe-hint {{
            position: absolute;
            bottom: 10px;
            left: 50%;
            transform: translateX(-50%);
            color: #444;
            font-size: 0.8em;
            animation: bounce 2s infinite;
        }}
        @keyframes bounce {{
            0%, 20%, 50%, 80%, 100% {{transform: translateX(-50%) translateY(0);}}
            40% {{transform: translateX(-50%) translateY(-10px);}}
            60% {{transform: translateX(-50%) translateY(-5px);}}
        }}
    </style>
</head>
<body>
    <div class="snap-container">
"""

if not results:
    html_content += """
        <div class="stock-card" style="align-items: center; text-align: center;">
            <h1 style="color: #666;">😴 今日無訊號</h1>
            <p style="color: #444; margin-top: 10px;">目前市場過熱或無符合條件個股<br>請明日再試</p>
        </div>
    """
else:
    for item in results:
        change_color = "up" if item['change'] >= 0 else "down"
        sign = "+" if item['change'] >= 0 else ""
        
        # 產生理由列表 HTML
        reasons_html = ""
        for r in item['reasons']:
            reasons_html += f"<li>{r}</li>"
            
        html_content += f"""
        <div class="stock-card">
            <div class="industry-badge">{item['industry']}</div>
            
            <div class="stock-header">
                <h1>{item['name']}</h1>
                <h2>{item['id']}</h2>
            </div>
            
            <div class="price-box">
                <span class="price">${item['price']}</span>
                <span class="change {change_color}">{sign}{item['change']}%</span>
            </div>
            
            <div class="signal-box">
                <div class="signal-title">{item['signal']}</div>
                <ul class="reason-list">
                    {reasons_html}
                </ul>
            </div>
            
            <div class="footer-info">
                <span class="rsi-val">RSI 強度: {item['rsi']}</span>
                <span>AI 偵測</span>
            </div>
            
            <div class="swipe-hint">往上滑動看下一檔 ▲</div>
        </div>
        """

html_content += """
    </div>
</body>
</html>
"""

with open("index.html", "w", encoding="utf-8") as f:
    f.write(html_content)
