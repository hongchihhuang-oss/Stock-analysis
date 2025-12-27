import yfinance as yf
import pandas as pd
import requests
from bs4 import BeautifulSoup
import ta
import twstock
import datetime
import time
import random

def get_stock_name(ticker):
    """
    利用 twstock 查詢股票中文名稱
    """
    try:
        # 去掉 .TW 或 .TWO，只留數字代號
        code = ticker.split('.')[0]
        if code in twstock.codes:
            return twstock.codes[code].name
    except:
        pass
    return ticker # 如果查不到就回傳代號

def get_volume_leaders():
    """
    爬取 Yahoo 股市成交量排行
    """
    print("🕷️ 正在爬取 Yahoo 股市人氣排行榜...")
    leaders = []
    
    try:
        urls = [
            "https://tw.stock.yahoo.com/rank/turnover?exchange=TAI", 
            "https://tw.stock.yahoo.com/rank/turnover?exchange=TWO"
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

        return leaders[:150] # 掃描前 150 名

    except Exception as e:
        print(f"❌ 爬蟲發生錯誤: {e}")
        return ['2330.TW', '2317.TW', '2603.TW']

def analyze_stock(ticker):
    try:
        df = yf.download(ticker, period="6mo", progress=False) # 改抓6個月，讓 MACD 更準
        
        if df.empty or len(df) < 35:
            return None

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # === 1. 取得基本資訊 ===
        stock_name = get_stock_name(ticker)
        
        # === 2. 計算深度技術指標 ===
        # A. 均線
        df['MA5'] = df['Close'].rolling(window=5).mean()
        df['MA20'] = df['Close'].rolling(window=20).mean()
        df['Vol_MA5'] = df['Volume'].rolling(window=5).mean()
        
        # B. RSI (相對強弱 - 溫度計)
        rsi_ind = ta.momentum.RSIIndicator(close=df['Close'], window=14)
        df['RSI'] = rsi_ind.rsi()
        
        # C. KD (隨機指標 - 短線買賣點)
        k_ind = ta.momentum.StochasticOscillator(high=df['High'], low=df['Low'], close=df['Close'], window=9, smooth_window=3)
        df['K'] = k_ind.stoch()
        df['D'] = k_ind.stoch_signal()
        
        # D. MACD (平滑異同移動平均線 - 波段趨勢)
        macd = ta.trend.MACD(close=df['Close'])
        df['MACD'] = macd.macd()
        df['MACD_Signal'] = macd.macd_signal()
        df['MACD_Hist'] = macd.macd_diff() # 柱狀圖

        # 取得最新資料
        today = df.iloc[-1]
        yesterday = df.iloc[-2]
        current_price = round(float(today['Close']), 2)
        current_rsi = round(float(today['RSI']), 1)
        current_k = round(float(today['K']), 1)
        
        # === 🛡️ 過熱保護 ===
        if current_rsi > 75:
            return None 

        # === 🧠 深度分析邏輯 ===
        signal = None
        reasons = []
        score = 0 # 建構一個評分系統 (滿分 5 星)
        
        # 1. 均線分析
        if today['Close'] > today['MA20']:
            score += 1
            if yesterday['MA5'] < yesterday['MA20'] and today['MA5'] > today['MA20']:
                reasons.append("MA黃金交叉 (短線轉強)")
                score += 1
        
        # 2. 成交量分析
        if today['Volume'] > today['Vol_MA5'] * 1.5:
            reasons.append("爆量 (資金湧入)")
            score += 1

        # 3. MACD 分析 (趨勢確認)
        # 柱狀圖由負轉正 (翻紅) 或是 雙線黃金交叉
        if yesterday['MACD_Hist'] < 0 and today['MACD_Hist'] > 0:
            reasons.append("MACD翻紅 (波段起漲)")
            score += 1.5
        elif yesterday['MACD'] < yesterday['MACD_Signal'] and today['MACD'] > today['MACD_Signal']:
            reasons.append("MACD交叉 (趨勢向上)")
            score += 1

        # 4. KD 分析 (買賣點)
        # K值在低檔 (50以下) 黃金交叉
        if current_k < 50 and yesterday['K'] < yesterday['D'] and today['K'] > today['D']:
            reasons.append("KD低檔金叉 (最佳買點)")
            score += 1.5

        # === 總結訊號 ===
        # 至少要有兩個好理由才顯示
        if len(reasons) >= 2 or score >= 3:
            if score >= 4:
                signal = "🔥 強力買進"
            elif "爆量" in reasons and "MACD" in str(reasons):
                signal = "🚀 量滾量上攻"
            else:
                signal = "🧐 值得關注"
                
            # 格式化輸出細節
            analysis_text = f"• RSI指標: {current_rsi} (安全)<br>"
            analysis_text += f"• KD數值: K({current_k})<br>"
            analysis_text += "• 觸發訊號: " + "、".join(reasons)

            return {
                "Code": ticker,
                "Name": stock_name,
                "Price": current_price,
                "Signal": signal,
                "Score": score,
                "Details": analysis_text
            }
        
        return None
            
    except Exception as e:
        return None

# === 主程式 ===
stock_list = get_volume_leaders()
print(f"共取得 {len(stock_list)} 檔人氣股票，開始深度分析...")

results = []
for i, stock in enumerate(stock_list):
    if i % 10 == 0:
        print(f"進度: {i}/{len(stock_list)}...")
    res = analyze_stock(stock)
    if res:
        results.append(res)

# 排序: 分數高的排前面
results.sort(key=lambda x: x['Score'], reverse=True)

# 產出 HTML
html_content = f"""
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI 深度選股報告 📊</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; padding: 20px; background-color: #f0f2f5; }}
        .container {{ max-width: 800px; margin: 0 auto; }}
        h1 {{ text-align: center; color: #1a1a1a; }}
        .summary {{ text-align: center; color: #666; margin-bottom: 30px; background: #fff; padding: 15px; border-radius: 10px; }}
        .card {{ background: white; padding: 20px; margin-bottom: 20px; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); position: relative; overflow: hidden; }}
        .card::before {{ content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 6px; }}
        .card.score-high::before {{ background-color: #d9534f; }} /* 高分紅條 */
        .card.score-mid::before {{ background-color: #f0ad4e; }} /* 中分橘條 */
        
        .header {{ display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 15px; border-bottom: 1px solid #eee; padding-bottom: 10px; }}
        .stock-info {{ display: flex; align-items: baseline; gap: 10px; }}
        .stock-name {{ font-size: 1.4em; font-weight: bold; color: #333; }}
        .stock-code {{ font-size: 0.9em; color: #888; }}
        .price {{ font-size: 1.5em; font-weight: bold; color: #333; }}
        
        .signal-badge {{ display: inline-block; padding: 5px 12px; border-radius: 20px; color: white; font-weight: bold; font-size: 0.9em; transform: translateY(-2px); }}
        .bg-red {{ background: linear-gradient(45deg, #e74c3c, #c0392b); box-shadow: 0 2px 5px rgba(231, 76, 60, 0.3); }}
        .bg-orange {{ background-color: #f39c12; }}
        
        .analysis-box {{ background-color: #f8f9fa; padding: 15px; border-radius: 8px; color: #555; line-height: 1.6; font-size: 0.95em; }}
        .score-star {{ color: #f1c40f; font-size: 1.2em; margin-left: auto; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 AI 深度選股報告</h1>
        <div class="summary">
            <b>今日掃描重點</b><br>
            成交量前 {len(stock_list)} 大熱門股｜濾除高風險 (RSI>75)<br>
            更新時間: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </div>
"""

if not results:
    html_content += "<div style='text-align:center; padding:50px;'>😴 今日大盤震盪，AI 建議多看少做，暫無高分標的。</div>"
else:
    for item in results:
        # 決定卡片樣式
        score_class = "score-mid"
        badge_class = "bg-orange"
        stars = "⭐" * int(item['Score'])
        
        if item['Score'] >= 4:
            score_class = "score-high"
            badge_class = "bg-red"
        
        html_content += f"""
        <div class="card {score_class}">
            <div class="header">
                <div class="stock-info">
                    <span class="stock-name">{item['Name']}</span>
                    <span class="stock-code">{item['Code']}</span>
                    <span class="signal-badge {badge_class}">{item['Signal']}</span>
                </div>
                <div style="display:flex; align-items:center; gap:10px;">
                    <span class="score-star">{stars}</span>
                    <span class="price">${item['Price']}</span>
                </div>
            </div>
            <div class="analysis-box">
                {item['Details']}
            </div>
        </div>
        """

html_content += """
    </div>
</body>
</html>
"""

with open("index.html", "w", encoding="utf-8") as f:
    f.write(html_content)
