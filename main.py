import os
import datetime
import feedparser
import yfinance as yf
import google.generativeai as genai

# 1. 初始化设置
DATE_STR = datetime.datetime.now().strftime("%Y-%m-%d")
# 获取 API Key，未获取到则中止运行
api_key = os.environ.get('GEMINI_API_KEY')
if not api_key:
    raise ValueError("未找到 GEMINI_API_KEY 环境变量，请检查 GitHub Secrets 配置。")

genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-1.5-flash') # 使用最新免费且快速的模型

# 2. 数据获取函数
def get_news():
    feeds = [
        "https://techcrunch.com/category/artificial-intelligence/feed/",
        "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=19854910" # 科技新闻备用源
    ]
    news_items = []
    for url in feeds:
        try:
            parsed = feedparser.parse(url)
            for entry in parsed.entries[:3]: # 每个源取前3条，避免超载
                news_items.append({"title": entry.title, "link": entry.link})
        except Exception as e:
            print(f"获取 RSS 失败 ({url}): {e}")
    return news_items

def get_stocks():
    tickers = ["NVDA", "MSFT", "GOOG"]
    stock_data = []
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="2d")
            if len(hist) >= 2:
                prev_close = hist['Close'].iloc[0]
                curr_close = hist['Close'].iloc[1]
                change = ((curr_close - prev_close) / prev_close) * 100
                stock_data.append({
                    "name": ticker,
                    "price": f"${curr_close:.2f}",
                    "change": f"{change:+.2f}%"
                })
        except Exception as e:
            print(f"获取股票数据失败 ({ticker}): {e}")
    return stock_data

def get_macro_calendar():
    # 硬编码简易宏观日历，预留后续扩展空间
    return [
        {"event": "美联储利率决议", "status": "本周无"},
        {"event": "美国非农就业数据", "status": "本周无"},
        {"event": "美国 CPI 数据", "status": "本周无"}
    ]

# 3. AI 处理函数
def analyze_news(news_items):
    analyzed_news = []
    for item in news_items:
        try:
            prompt = (
                f"请分析这条新闻标题：'{item['title']}'。\n"
                "1. 评估其对科技/AI行业的重要程度，必须严格输出：🔴高 或 🟡中 或 🟢低。\n"
                "2. 提供50字以内的中文客观摘要，保持审慎中性的风格。\n"
                "格式要求：[重要程度] 摘要内容"
            )
            response = model.generate_content(prompt)
            result_text = response.text.strip()
            
            # 简单解析返回结果
            level = "🟡中" # 默认值
            if "🔴高" in result_text: level = "🔴高"
            elif "🟢低" in result_text: level = "🟢低"
            
            summary = result_text.split("]", 1)[-1].strip() if "]" in result_text else result_text
            
            analyzed_news.append({
                "title": item['title'],
                "link": item['link'],
                "level": level,
                "summary": summary
            })
        except Exception as e:
            print(f"AI 处理新闻失败 ({item['title']}): {e}")
            analyzed_news.append({
                "title": item['title'],
                "link": item['link'],
                "level": "⚪未知",
                "summary": "处理时发生系统读取错误。"
            })
            
    # 按重要程度排序（🔴高 -> 🟡中 -> 🟢低 -> ⚪未知）
    sort_order = {"🔴高": 1, "🟡中": 2, "🟢低": 3, "⚪未知": 4}
    analyzed_news.sort(key=lambda x: sort_order.get(x['level'], 5))
    return analyzed_news

# 4. 生成 HTML 报告
def generate_html(news, stocks, calendar):
    top_news = [n for n in news if n['level'] == "🔴高"][:3]
    if not top_news:
        top_news = news[:3] # 若无高优新闻，则取前三条

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
    
    # 确保目录存在
    os.makedirs("report", exist_ok=True)
    
    # 保存每日独立报告
    report_path = f"report/{DATE_STR}.html"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html_output)
        
    # 覆盖 index.html 以供 GitHub Pages 默认展示最新内容
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_output)
        
    print("系统运行结束。")
