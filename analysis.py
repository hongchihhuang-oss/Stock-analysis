import yfinance as yf
import pandas as pd
import requests
from bs4 import BeautifulSoup
import ta
import datetime
import time
import random

def get_volume_leaders():
    """
    爬取 Yahoo 股市「成交量排行榜」的前 150 名股票
    """
    print("🕷️ 正在爬取 Yahoo 股市人氣排行榜...")
    leaders = []
    
    try:
        urls = [
            "https://tw.stock.yahoo.com/rank/turnover?exchange=TAI", # 上市
            "https://tw.stock.yahoo.com/rank/turnover?exchange=TWO"  # 上櫃
        ]
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

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
            
            print(f"目前已找到 {len(leaders)} 檔熱門股...")
            time.sleep(1)

        return leaders[:150]

    except Exception as e:
        print(f"❌ 爬蟲發生錯誤: {e}")
        return ['2330.TW', '2317.TW', '2454.TW'] # 發生錯誤時的備用清單

def analyze_stock(ticker):
    try:
        # 下載資料
        df = yf.download(ticker, period="3mo", progress=False)
        
        if df.empty or len(df) < 20:
            return None

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # === 計算技術指標 ===
        # 1. 均線與成交量
        df['MA5'] = df['Close'].rolling(window=5).mean()
        df['MA20'] = df['Close'].rolling(window=20).mean()
        df['Vol_MA5'] = df['Volume'].rolling(window=5).mean()
        
        # 2. RSI 指標 (溫度計)
        # 使用 ta 套件計算 RSI，參數通常設 14 天
        rsi_indicator = ta.momentum.RSIIndicator(close=df['Close'], window=14)
        df['RSI'] = rsi_indicator.rsi()
        
        today = df.iloc[-1]
        yesterday = df.iloc[-2]
        current_price = round(float(today['Close']), 2)
        current_rsi = round(float(today['RSI']), 1)
        
        # === 🛡️ 過熱保護機制 🛡️ ===
        # 如果 RSI > 75，代表已經過熱，直接過濾掉，不看它了
        if current_rsi > 75:
            # 這裡我們選擇直接回傳 None (跳過)，或是你可以選擇回傳一個「過熱警告」
            # 為了安全起見，我們這裡直接跳過，不讓它出現在清單上誘惑你
            return None 

        # === 進場邏輯判斷 ===
        signal = None
        reasons = []
        
        # 條件 A: 黃金交叉
        if yesterday['MA5'] < yesterday['MA20'] and today['MA5'] > today['MA20']:
            reasons.append("黃金交叉")
            
        # 條件 B: 爆量 (今天量 > 5日均量 1.5 倍)
        if today['Volume'] > today['Vol_MA5'] * 1.5:
            reasons.append("單日爆量")

        # 綜合篩選
        if "黃金交叉" in reasons:
            signal = "✨ 轉強關注"
            if "單日爆量" in reasons:
                signal = "🔥 爆量起漲"
        elif "單日爆量" in reasons and today['Close'] > today['MA20']:
             signal = "🚀 量增價強"

        if signal:
            # 把 RSI 數值也顯示在理由中，讓你參考
            reasons.append(f"RSI: {current_rsi}")
            
            return {
                "Stock": ticker,
                "Price": current_price,
                "Signal": signal,
                "Details": " | ".join(reasons)
            }
        
        return None
            
    except Exception as e:
        return None

# === 主程式 ===
stock_list = get_volume_leaders()
print(f"共取得 {len(stock_list)} 檔人氣股票，開始分析...")

results = []
for i, stock in enumerate(stock_list):
    if i % 10 == 0:
        print(f"進度: {i}/{len(stock_list)}...")
    
    res = analyze_stock(stock)
    if res:
        results.append(res)

# 排序
results.sort(key=lambda x: (x['Signal'] != "🔥 爆量起漲", x['Signal']))

# 產出 HTML
html_content = f"""
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI 人氣王雷達 (含過熱保護) 🛡️</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; padding: 20px; background-color: #f4f6f8; }}
        .container {{ max-width: 800px; margin: 0 auto; }}
        h1 {{ text-align: center; color: #2c3e50; }}
        .summary {{ text-align: center; color: #666; margin-bottom: 20px; }}
        .card {{ background: white; padding: 20px; margin-bottom: 15px; border-radius: 12px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); border-left: 6px solid #ccc; }}
        .card.buy {{ border-left-color: #e74c3c; }}
        .card.watch {{ border-left-color: #f39c12; }}
        .stock-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }}
        .stock-id {{ font-size: 1.5em; font-weight: bold; color: #2c3e50; }}
        .stock-price {{ font-size: 1.3em; font-weight: bold; color: #2c3e50; }}
        .signal-tag {{ padding: 5px 10px; border-radius: 20px; color: white; font-weight: bold; font-size: 0.9em; }}
        .tag-buy {{ background: linear-gradient(45deg, #e74c3c, #c0392b); }}
        .tag-watch {{ background-color: #f39c12; }}
        .details {{ color: #7f8c8d; font-size: 0.95em; margin-top: 5px; }}
        .safe-badge {{ display: inline-block; background-color: #e8f5e9; color: #2e7d32; font-size: 0.8em; padding: 2px 6px; border-radius: 4px; margin-left: 10px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🛡️ AI 人氣王雷達 <span style="font-size:0.6em; color:#777;">(已過濾高風險股)</span></h1>
        <p class="summary">
            掃描範圍: 今日成交量前 {len(stock_list)} 名<br>
            篩選標準: 趨勢轉強 + <b>RSI < 75 (未過熱)</b><br>
            發現機會: {len(results)} 檔<br>
            更新時間: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </p>
"""

if not results:
    html_content += "<p style='text-align:center'>🛡️ 目前熱門股中，符合訊號且「未過熱」的標的很少，建議空手觀望。</p>"
else:
    for item in results:
        tag_class = "tag-watch"
        card_class = "watch"
        if "爆量" in item['Signal'] or "起漲" in item['Signal']:
            tag_class = "tag-buy"
            card_class = "buy"
            
        html_content += f"""
        <div class="card {card_class}">
            <div class="stock-header">
                <div>
                    <span class="stock-id">{item['Stock']}</span>
                    <span class="safe-badge">Safe (RSI < 75)</span>
                </div>
                <span class="signal-tag {tag_class}">{item['Signal']}</span>
                <span class="stock-price">${item['Price']}</span>
            </div>
            <div class="details">{item['Details']}</div>
        </div>
        """

html_content += """
    </div>
</body>
</html>
"""

with open("index.html", "w", encoding="utf-8") as f:
    f.write(html_content)
