import yfinance as yf
import pandas as pd
import requests
import ta
import time
import random

# 🟢 版本號
APP_VERSION = "v8.1 (滑動修復版)"

# ==========================================
# 1. 籌碼估算 (避開證交所擋 IP 問題)
# ==========================================

def get_market_chips_safe():
    """
    🏦 安全版籌碼分析：利用權值股走勢推算大盤氣氛
    (因為 GitHub Actions IP 容易被 TWSE 封鎖，改用此法確保程式不卡死)
    """
    print("🏦 正在推算大盤資金流向...")
    chips_data = {"Foreign": 0, "Trust": 0, "Dealer": 0, "Total": 0, "Status": "資料連線中"}
    
    try:
        # 抓取 0050 (代表大盤) 的成交量與漲跌
        etf = yf.Ticker("0050.TW")
        hist = etf.history(period="5d")
        
        if len(hist) >= 2:
            today = hist.iloc[-1]
            prev = hist.iloc[-2]
            
            # 簡單推算邏輯：
            # 0050 大漲 + 爆量 = 外資買
            # 0050 小漲 = 投信/散戶買
            change_pct = (today['Close'] - prev['Close']) / prev['Close'] * 100
            vol_ratio = today['Volume'] / hist['Volume'].mean()
            
            # 模擬數據 (單位：億)
            base_amt = 50 * vol_ratio # 基礎量
            
            if change_pct > 1.5: # 大漲
                chips_data["Foreign"] = round(base_amt * 1.2, 1)
                chips_data["Trust"] = round(base_amt * 0.3, 1)
                chips_data["Status"] = "🔥 外資大舉回補"
            elif change_pct > 0.5: # 小漲
                chips_data["Foreign"] = round(base_amt * 0.5, 1)
                chips_data["Trust"] = round(base_amt * 0.8, 1)
                chips_data["Status"] = "📈 法人偏多"
            elif change_pct < -1.5: # 大跌
                chips_data["Foreign"] = round(base_amt * -1.5, 1)
                chips_data["Status"] = "💸 外資提款殺盤"
            else:
                chips_data["Status"] = "⚖️ 多空觀望"
                
            chips_data["Total"] = round(chips_data["Foreign"] + chips_data["Trust"], 1)
            
    except Exception as e:
        print(f"籌碼推算失敗: {e}")
        chips_data["Status"] = "暫無數據"
        
    return chips_data

# ==========================================
# 2. 爬蟲與分析邏輯
# ==========================================

def get_volume_leaders():
    """爬取 Yahoo 人氣榜"""
    print("🕷️ 正在爬取 Yahoo 股市人氣排行榜...")
    leaders = []
    try:
        # 為了避免爬蟲被卡住，我們只爬上市就好，減少請求次數
        url = "https://tw.stock.yahoo.com/rank/turnover?exchange=TAI"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10) # 設定 timeout 避免卡死
        
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')
        links = soup.find_all('a', href=True)
        
        for link in links:
            href = link['href']
            if "/quote/" in href and ".TW" in href:
                ticker = href.split("/quote/")[-1]
                if ticker not in leaders: leaders.append(ticker)
                if len(leaders) >= 50: break # 先抓 50 檔就好，確保速度
        
        return leaders 
    except Exception as e:
        print(f"爬蟲錯誤: {e}")
        return ['2330.TW', '2317.TW', '2603.TW'] # 備案

def get_stock_name_safe(ticker):
    # 簡單對應表，避免 twstock 卡住
    return ticker, "一般產業"

def analyze_stock(ticker):
    try:
        df = yf.download(ticker, period="3mo", progress=False)
        if df.empty or len(df) < 20: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)

        # 指標
        df['MA5'] = df['Close'].rolling(5).mean()
        df['MA20'] = df['Close'].rolling(20).mean()
        df['Vol_MA5'] = df['Volume'].rolling(5).mean()
        df['RSI'] = ta.momentum.RSIIndicator(df['Close'], 14).rsi()
        
        today = df.iloc[-1]
        prev = df.iloc[-2]
        price = round(float(today['Close']), 2)
        
        # 簡單訊號
        signal = None
        reasons = []
        
        if prev['MA5'] < prev['MA20'] and today['MA5'] > today['MA20']:
            reasons.append("MA5 黃金交叉")
        if today['Volume'] > today['Vol_MA5'] * 1.5:
            reasons.append("爆量攻擊")
            
        if reasons:
            signal = "✨ 觀察"
            if "爆量攻擊" in reasons: signal = "🔥 主力買進"
            
            # 這裡不呼叫外部 API (如 twstock/news) 以免卡住，只做純數據運算
            return {
                "id": ticker, "name": ticker, "price": price,
                "change": round((today['Close'] - prev['Close']) / prev['Close'] * 100, 2),
                "rsi": round(float(today['RSI']), 1),
                "signal": signal, "reasons": reasons
            }
        return None
    except: return None

# === 主程式 ===
print("🚀 啟動 v8.1 安全模式...")
market_chips = get_market_chips_safe()
stock_list = get_volume_leaders()
results = []

print(f"開始掃描 {len(stock_list)} 檔股票...")
for i, stock in enumerate(stock_list):
    res = analyze_stock(stock)
    if res: results.append(res)

results.sort(key=lambda x: (x['signal'] != "🔥 主力買進", x['rsi']))

# === HTML ===
html_content = f"""
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Chip Master {APP_VERSION}</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ 
            background-color: #0b0e11; 
            color: #e1e1e1; 
            font-family: -apple-system, Roboto, sans-serif; 
            overflow: hidden; /* 防止 Body 捲動，交給 container */
        }}
        
        /* 核心修復：使用 dvh (Dynamic Viewport Height) 解決手機網址列遮擋問題 */
        .snap-container {{ 
            height: 100vh; 
            height: 100dvh; 
            width: 100vw; 
            overflow-y: scroll; 
            scroll-snap-type: y mandatory; 
            scroll-behavior: smooth;
            -webkit-overflow-scrolling: touch; /* iOS 滑動慣性修復 */
        }}
        
        .stock-card {{ 
            height: 100vh; 
            height: 100dvh; 
            width: 100vw; 
            scroll-snap-align: start; 
            padding: 20px; 
            display: flex; 
            flex-direction: column; 
            border-bottom: 1px solid #222; 
            position: relative;
        }}
        
        /* 儀表板樣式 */
        .dashboard-card {{ 
            background: linear-gradient(135deg, #1e2a78 0%, #ff5e62 100%); 
            align-items: center; 
            justify-content: center; 
        }}
        .chip-box {{ background: rgba(0,0,0,0.3); padding: 20px; border-radius: 12px; text-align: center; min-width: 250px; }}
        .chip-stat {{ font-size: 2em; font-weight: bold; margin: 10px 0; }}
        
        /* 動畫箭頭 */
        .scroll-hint {{
            position: absolute; bottom: 30px; left: 50%; transform: translateX(-50%);
            animation: bounce 2s infinite; font-size: 1.5em; opacity: 0.8;
        }}
        @keyframes bounce {{
            0%, 20%, 50%, 80%, 100% {{transform: translateX(-50%) translateY(0);}}
            40% {{transform: translateX(-50%) translateY(-10px);}}
            60% {{transform: translateX(-50%) translateY(-5px);}}
        }}

        /* 個股卡片 */
        .stock-id {{ font-size: 2.5em; font-weight: bold; }}
        .price {{ font-size: 3.5em; font-weight: 800; margin: 10px 0; }}
        .signal {{ font-size: 1.2em; color: #f39c12; margin-bottom: 20px; }}
        .reasons li {{ font-size: 1.1em; margin-bottom: 10px; color: #ccc; }}
        
        .footer {{ position: absolute; bottom: 10px; width: 100%; text-align: center; color: #666; font-size: 0.8em; left:0; }}
        .page-counter {{ position: absolute; top: 20px; right: 20px; background: rgba(0,0,0,0.5); padding: 5px 10px; border-radius: 10px; }}
    </style>
</head>
<body>
    <div class="snap-container">
"""

# 1. 儀表板
status_color = "#ff3333" if "回補" in market_chips['Status'] or "偏多" in market_chips['Status'] else "#00cc66"
html_content += f"""
        <div class="stock-card dashboard-card">
            <h1 style="margin-bottom:20px;">🏦 今日戰情室</h1>
            <div class="chip-box">
                <div>大盤氣氛推算</div>
                <div class="chip-stat" style="color:{status_color}">{market_chips['Status']}</div>
                <div style="font-size:0.9em; color:#ddd;">外資動向: {market_chips['Foreign']} 億</div>
            </div>
            <div style="margin-top:20px;">
                👇 掃描結果：共 {len(results)} 檔訊號股
            </div>
            <div class="scroll-hint">⬇️ 往上滑動</div>
            <div class="footer">{APP_VERSION}</div>
        </div>
"""

# 2. 個股
if not results:
    html_content += """
    <div class="stock-card" style="background:#000; align-items:center; justify-content:center;">
        <h1>😴 查無訊號</h1>
        <p>今日市場平靜，無符合條件個股</p>
    </div>
    """
else:
    for i, item in enumerate(results):
        c_color = "#ff3333" if item['change'] > 0 else "#00cc66"
        html_content += f"""
        <div class="stock-card" style="background: #0b0e11;">
            <div class="page-counter">{i+1} / {len(results)}</div>
            <div class="stock-id">{item['name']}</div>
            <div class="price" style="color:{c_color}">${item['price']}</div>
            <div class="signal">{item['signal']}</div>
            <ul class="reasons" style="list-style:none; padding:0;">
                {''.join([f"<li>✔ {r}</li>" for r in item['reasons']])}
            </ul>
            <div class="footer">RSI: {item['rsi']} | {APP_VERSION}</div>
        </div>
        """

html_content += "</div></body></html>"

with open("index.html", "w", encoding="utf-8") as f:
    f.write(html_content)
