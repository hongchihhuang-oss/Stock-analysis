import yfinance as yf
import pandas as pd
import ta
import datetime

# 1. 設定你想監控的股票清單
stock_list = ['2330.TW', '2317.TW', '2454.TW', '0050.TW'] 

def analyze_stock(ticker):
    try:
        # 下載資料 (增加錯誤處理參數)
        print(f"正在分析: {ticker}...")
        df = yf.download(ticker, period="1y", progress=False)
        
        # 檢查資料是否為空
        if df.empty:
            return {
                "Stock": ticker, "Price": 0,
                "Signal": "❌ 資料錯誤", "Details": "下載到的資料是空的 (Empty Data)"
            }

        # 處理 MultiIndex 問題 (新版 yfinance 可能會有多層欄位)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # 檢查資料長度
        if len(df) < 20:
            return {
                "Stock": ticker, "Price": 0,
                "Signal": "❌ 資料不足", "Details": f"資料筆數太少 (只有 {len(df)} 筆)"
            }

        # 2. 計算技術指標
        df['MA5'] = df['Close'].rolling(window=5).mean()
        df['MA20'] = df['Close'].rolling(window=20).mean()
        df['Vol_MA5'] = df['Volume'].rolling(window=5).mean()
        
        # 取得昨天與今天
        today = df.iloc[-1]
        yesterday = df.iloc[-2]
        
        # 取得目前股價
        current_price = round(float(today['Close']), 2)
        
        # 3. 判斷進場訊號
        signal = "👀 觀望中"
        reasons = []
        
        # 條件 A: 黃金交叉
        if yesterday['MA5'] < yesterday['MA20'] and today['MA5'] > today['MA20']:
            reasons.append("黃金交叉 (短線轉強)")
            
        # 條件 B: 站上月線
        if today['Close'] > today['MA20']:
            reasons.append("站上月線 (趨勢向上)")

        # 條件 C: 爆量
        if today['Volume'] > today['Vol_MA5'] * 1.5:
            reasons.append("成交爆量")

        # 綜合判斷
        if "黃金交叉 (短線轉強)" in reasons and "成交爆量" in reasons:
            signal = "🔥 強力買進"
        elif "黃金交叉 (短線轉強)" in reasons:
            signal = "✨ 買進訊號"
        elif len(reasons) > 0:
            signal = "🧐 關注"
            
        return {
            "Stock": ticker,
            "Price": current_price,
            "Signal": signal,
            "Details": " | ".join(reasons) if reasons else "目前無特殊訊號"
        }
            
    except Exception as e:
        return {
            "Stock": ticker,
            "Price": 0,
            "Signal": "❌ 程式錯誤",
            "Details": f"錯誤原因: {str(e)}"
        }

# 執行分析
results = []
for stock in stock_list:
    res = analyze_stock(stock)
    results.append(res) # 不管有沒有結果，都加進去顯示

# 4. 產出 HTML
html_content = f"""
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI 股市雷達 📡</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; padding: 20px; background-color: #f0f2f5; }}
        .container {{ max-width: 600px; margin: 0 auto; }}
        h1 {{ text-align: center; color: #1a1a1a; margin-bottom: 10px; }}
        .time {{ text-align: center; color: #65676b; font-size: 0.8em; margin-bottom: 30px; }}
        .card {{ background: white; padding: 20px; margin-bottom: 15px; border-radius: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .card-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }}
        .stock-name {{ font-size: 1.2em; font-weight: bold; color: #1a1a1a; }}
        .price {{ font-size: 1.2em; font-weight: bold; color: #1a1a1a; }}
        .signal {{ font-weight: bold; padding: 5px 10px; border-radius: 6px; display: inline-block; }}
        .buy {{ background-color: #e7f3ff; color: #1877f2; }}
        .watch {{ background-color: #fff3e0; color: #f29339; }}
        .error {{ background-color: #ffebee; color: #c62828; }}
        .details {{ color: #65676b; font-size: 0.9em; margin-top: 8px; line-height: 1.4; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📈 AI 選股雷達</h1>
        <p class="time">更新時間: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
"""

for item in results:
    style_class = "watch"
    if "買進" in item['Signal']:
        style_class = "buy"
    elif "錯誤" in item['Signal']:
        style_class = "error"
        
    html_content += f"""
        <div class="card">
            <div class="card-header">
                <span class="stock-name">{item['Stock']}</span>
                <span class="price">${item['Price']}</span>
            </div>
            <div class="signal {style_class}">{item['Signal']}</div>
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
