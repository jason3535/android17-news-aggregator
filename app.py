"""
Android 17 News Aggregator
Flask 应用主入口
"""

from flask import Flask, render_template, jsonify, request
from apscheduler.schedulers.background import BackgroundScheduler
from scraper import scrape_all, load_news
from translator import translate_text
import atexit

app = Flask(__name__)

# 配置定时任务
scheduler = BackgroundScheduler()
scheduler.add_job(func=scrape_all, trigger="interval", hours=1, id='scrape_job')
scheduler.start()

# 确保退出时关闭调度器
atexit.register(lambda: scheduler.shutdown())


@app.route('/')
def index():
    """主页 - 新闻 Feed 流"""
    return render_template('index.html')


@app.route('/api/news')
def get_news():
    """API - 获取新闻数据"""
    data = load_news()
    return jsonify(data)


@app.route('/api/refresh')
def refresh_news():
    """API - 手动刷新新闻"""
    data = scrape_all()
    return jsonify(data)


@app.route('/api/status')
def status():
    """API - 获取系统状态"""
    data = load_news()
    return jsonify({
        'status': 'running',
        'last_updated': data.get('last_updated'),
        'total_items': data.get('total_count', 0),
        'scheduler_running': scheduler.running
    })


@app.route('/api/translate', methods=['POST'])
def translate():
    """API - 翻译文本"""
    data = request.get_json()
    text = data.get('text', '')
    target_lang = data.get('target', 'zh-CN')

    translated = translate_text(text, target_lang)
    return jsonify({'translated': translated})


if __name__ == '__main__':
    # 启动时先爬取一次
    print("正在获取最新 Android 17 新闻...")
    scrape_all()
    print("启动 Web 服务器...")
    app.run(debug=True, port=5001)
