"""
Android 17 News Aggregator
Flask 应用主入口
"""

from flask import Flask, render_template, jsonify, request
from apscheduler.schedulers.background import BackgroundScheduler
from scraper import scrape_all, load_news
from translator import translate_text
import atexit
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

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


@app.route('/preview')
def preview():
    """预览页面 - 新架构设计"""
    data = load_news()
    return render_template('preview_dynamic.html', news_data=data)


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


def run_scheduler():
    """启动定时任务调度器"""
    if not scheduler.running:
        scheduler.start()
        atexit.register(lambda: scheduler.shutdown())

def initialize_data():
    """初始化数据 - 只在主进程中运行一次"""
    print("正在获取最新 Android 17 新闻...")
    scrape_all()

if __name__ == '__main__':
    # 本地开发运行
    initialize_data()
    run_scheduler()
    print("启动 Web 服务器...")
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=False)
else:
    # 生产环境（如 gunicorn）
    # 只在主 worker 中启动调度器
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true' or os.environ.get('IS_MAIN_PROCESS') == 'true':
        initialize_data()
        run_scheduler()
