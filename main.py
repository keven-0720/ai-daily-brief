import os
import json
import datetime
import feedparser
import yfinance as yf
from google import genai # 使用全新 SDK

# 1. 初始化设置
DATE_STR = datetime.datetime.now().strftime("%Y-%m-%d")
api_key = os.environ.get('GEMINI_API_KEY')
if not api_key:
    raise ValueError("未找到 GEMINI_API_KEY 环境变量，请检查 GitHub Secrets 配置。")

# 初始化新版客户端
client = genai.Client(api_key=api_key)
# 采用当前最新稳定且免费的模型
MODEL_NAME = 'gemini-2.5-flash' 

# 2. 数据获取函数 (保持不变)
def get_news():
    feeds = [
        "https://techcrunch.com/category/artificial-intelligence/feed/",
        "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=19854910"
    ]
    news_items = []
    for url in feeds:
        try:
            parsed = feedparser.parse(url)
            for entry in parsed.entries[:3]:
                news_items.append({"title": entry.title, "link": entry.link})
        except Exception as e:
            print(f"获取 RSS 失败 ({url}): {e}")
    return news_items

def get_stocks():
    tickers = ["NVDA", "MSFT", "GOOG", "MU", "DELL"]
    stock_data = []
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="5d") # 使用5天以防周末停盘
            if len(hist) >= 2:
                prev_close = hist['Close'].iloc[-2]
                curr_close = hist['Close'].iloc[-1]
                change = ((curr_close - prev_close) / prev_close) * 100
                stock_data.append({
                    "name": ticker,
                    "price": f"${curr_close:.2f}",
                    "change": f"{change:+.2f}%"
                })
        except Exception as e:
            print(f"获取股票数据异常 ({ticker}): {e}")
    return stock_data

def get_macro_calendar():
    return [
        {"event": "美联储利率决议", "status": "本周无"},
        {"event": "美国非农就业数据", "status": "本周无"},
        {"event": "美国 CPI 数据", "status": "本周无"}
    ]

# 3. AI 处理函数 (核心重构区)
def analyze_news(news_items):
    analyzed_news = []
    for item in news_items:
        try:
            # 采用强约束的 JSON Prompt
            prompt = f"""
请分析这条新闻标题：'{item['title']}'。
请评估其对科技/AI行业的重要程度，并给出50字以内中文摘要，保持审慎中性的风格。
请严格仅返回以下 JSON 格式（不要输出任何其他内容）：
{{
  "level": "🔴高", // 只能在 🔴高, 🟡中, 🟢低 中选一
  "summary": "你的摘要内容"
}}
"""
            # 新版接口调用方式
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt
            )
            
            # 安全提取文本：防范抛错
            if hasattr(response, "text") and response.text:
                result_text = response.text.strip()
            else:
                result_text = str(response)
                
            # 清理 AI 有时附带的 Markdown 代码块标记
            if result_text.startswith("```json"):
                result_text = result_text[7:-3].strip()
            elif result_text.startswith("```"):
                result_text = result_text[3:-3].strip()
                
            # 解析 JSON
            try:
                data = json.loads(result_text)
                level = data.get("level", "🟡中")
                summary = data.get("summary", "未能生成摘要。")
            except Exception as parse_err:
                print(f"JSON 解析失败: {parse_err}, 原始文本: {result_text}")
                level = "🟡中"
                summary = result_text.replace("\n", " ") # 降级处理，直接取文本
            
            # 数据校验
            if "高" in level: level = "🔴高"
            elif "低" in level: level = "🟢低"
            else: level = "🟡中"

            analyzed_news.append({
                "title": item['title'],
                "link": item['link'],
                "level": level,
                "summary": summary
            })
            
        except Exception as e:
            print(f"AI 处理新闻异常 ({item['title']}): {e}")
            analyzed_news.append({
                "title": item['title'],
                "link": item['link'],
                "level": "⚪未知",
                "summary": "接口响应异常，未能完成解析。"
            })
            
    # 排序逻辑
    sort_order = {"🔴高": 1, "🟡中": 2, "🟢低": 3, "⚪未知": 4}
    analyzed_news.sort(key=lambda x: sort_order.get(x['level'], 5))
    return analyzed_news

# 4. 生成 HTML 报告 (保持不变)
def generate_html(news, stocks, calendar):
    top_news = [n for n in news if n['level'] == "🔴高"][:3]
    if not top_news:
        top_news = news[:3]

    html_content = f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>每日 AI 情报看板 - {DATE_STR}</title>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #333; max-width: 900px; margin: 0 auto; padding: 20px; background-color: #f9f9f9; }}
            h1, h2 {{ color: #2c3e50; border-bottom: 2px solid #eee; padding-bottom: 5px; }}
            .card {{ background: #fff; padding: 15px; margin-bottom: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }}
            .highlight {{ border-left: 4px solid #e74c3c; }}
            .stock-up {{ color: #e74c3c; font-weight: bold; }}
            .stock-down {{ color: #27ae60; font-weight: bold; }}
            .tag {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.85em; margin-right: 10px; background: #eee; }}
            a {{ color: #3498db; text-decoration: none; }}
            a:hover {{ text-decoration: underline; }}
        </style>
    </head>
    <body>
        <h1>📊 每日情报看板 ({DATE_STR})</h1>
        
        <h2>📌 核心摘要 (Top 3)</h2>
        <div class="card highlight">
            <ul>
                {"".join(f"<li><strong>{n['level']}</strong> <a href='{n['link']}' target='_blank'>{n['title']}</a><br>{n['summary']}</li>" for n in top_news)}
            </ul>
        </div>

        <h2>📈 重点市场标的</h2>
        <div class="card">
            <table width="100%" style="text-align: left;">
                <tr><th>标的</th><th>最新价格</th><th>日内变动</th></tr>
                {"".join(f"<tr><td>{s['name']}</td><td>{s['price']}</td><td class='{'stock-up' if '+' in s['change'] else 'stock-down'}'>{s['change']}</td></tr>" for s in stocks)}
            </table>
        </div>

        <h2>📰 情报追踪</h2>
        <div class="card">
            {"".join(f"<p><span class='tag'>{n['level']}</span> <a href='{n['link']}' target='_blank'>{n['title']}</a><br><span style='color:#666;font-size:0.9em;'>{n['summary']}</span></p>" for n in news)}
        </div>

        <h2>📅 宏观前瞻</h2>
        <div class="card">
            <ul>
                {"".join(f"<li>{c['event']}: {c['status']}</li>" for c in calendar)}
            </ul>
        </div>
        
        <p style="text-align: center; color: #999; font-size: 0.8em;">由自动化系统生成 | 仅供内部参考</p>
    </body>
    </html>
    """
    return html_content

# 5. 主程序执行流程
if __name__ == "__main__":
    print("开始获取数据...")
    news_data = get_news()
    stock_data = get_stocks()
    calendar_data = get_macro_calendar()
    
    print("开始 AI 分析...")
    analyzed_news = analyze_news(news_data)
    
    print("生成并保存报告...")
    html_output = generate_html(analyzed_news, stock_data, calendar_data)
    
    os.makedirs("report", exist_ok=True)
    
    report_path = f"report/{DATE_STR}.html"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html_output)
        
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_output)
        
    print("系统运行结束。")
