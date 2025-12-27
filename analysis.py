import yfinance as yf
import pandas as pd
import ta
import datetime

# 1. 設定你想監控的股票清單 (台股代號要加 .TW)
stock_list = ['2330.TW', '2317.TW', '2454.TW', '0050.TW'] 

def analyze_stock(ticker):
    try:
        # 下載最近 1 年的資料
        df = yf.download(ticker, period="1y")
        
        # 檢查資料是否足夠
        if len(df) < 20:
            return None

        # 2. 計算技術指標
        # 均線 (MA)
        df['MA5'] = df['Close'].rolling(window=5).mean()
        df['MA20'] = df['Close'].rolling(window=20).mean()
        
        # 成交量變動 (用來模擬籌碼熱度)
        df['Vol_MA5'] = df['Volume'].rolling(window=5).mean()
        
        # 取得昨天與今天的資料
        today = df.iloc[-1]
        yesterday = df.iloc[-2]
        
        # 3. 判斷進場訊號
        signal = "觀望"
        reasons = []
        
        # 條件 A: 黃金交叉 (昨天的 5日線 < 20日線，且 今天的 5日線 > 20日線)
        if yesterday['MA5'] < yesterday['MA20'] and today['MA5'] > today['MA20']:
            reasons.append("出現黃金交叉 (短線轉強)")
            
        # 條件 B: 站上月線 (股價 > 20日均線)
        if today['Close'] > today['MA20']:
            reasons.append("股價站上月線 (趨勢向上)")

        # 條件 C: 爆量 (今天成交量 > 5日均量 1.5倍) - 模擬主力進場
        if today['Volume'] > today['Vol_MA5'] * 1.5:
            reasons.append("成交量爆量 (大人在照顧)")

        # 綜合判斷：如果是黃金交叉 且 有爆量
        if "出現黃金交叉 (短線轉強)" in reasons and "成交量爆量 (大人在照顧)" in reasons:
            signal = "🔥 強力買進訊號"
        elif "出現黃金交叉 (短線轉強)" in reasons:
            signal = "✨ 關注 (黃金交叉)"
            
        return {
            "Stock": ticker,
            "Price": round(today['Close'], 2),
            "Signal": signal,
            "Details": ", ".join(reasons)
        }
            
    except Exception as e:
        print(f"Error analyzing {ticker}: {e}")
        return None

# 執行分析
results = []
for stock in stock_list:
    res = analyze_stock(stock)
    if res:
        results.append(res)

# 4. 產出 HTML 網頁
html_content = f"""
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI 股市雷達 📡</title>
    <style>
        body {{ font-family: Arial, sans-serif; padding: 20px; background-color: #f4f4f9; }}
        h1 {{ color: #333; text-align: center; }}
        .card {{ background: white; padding: 15px; margin-bottom: 10px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
        .signal-buy {{ color: #d9534f; font-weight: bold; font-size: 1.2em; }}
        .signal-watch {{ color: #f0ad4e; font-weight: bold; }}
        .price {{ float: right; color: #555; }}
        .update-time {{ text-align: center; color: #888; font-size: 0.8em; }}
    </style>
</head>
<body>
    <h1>📈 AI 選股雷達</h1>
    <p class="update-time">更新時間: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    
"""

for item in results:
    color_class = "signal-watch"
    if "買進" in item['Signal']:
        color_class = "signal-buy"
    
    html_content += f"""
    <div class="card">
        <h3>{item['Stock']} <span class="price">${item['Price']}</span></h3>
        <p class="{color_class}">{item['Signal']}</p>
        <p style="color: #666; font-size: 0.9em;">{item['Details']}</p>
    </div>
    """

html_content += "</body></html>"

# 儲存為 index.html
with open("index.html", "w", encoding="utf-8") as f:
    f.write(html_content)

print("分析完成，網頁已生成！")
