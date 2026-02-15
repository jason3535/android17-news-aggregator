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


@app.route('/api/share', methods=['POST'])
def create_share():
    """API - 创建分享链接"""
    import uuid
    import json
    from pathlib import Path
    from datetime import datetime as dt
    from summarizer import generate_smart_summary, generate_bullet_summary

    data = request.get_json()
    news_item = data.get('news_item')

    if not news_item:
        return jsonify({'error': 'No news item provided'}), 400

    # 生成唯一分享ID
    share_id = str(uuid.uuid4())[:8]

    # 生成AI总结
    try:
        ai_summary = generate_smart_summary(news_item)
        bullet_points = generate_bullet_summary(news_item)
    except Exception as e:
        print(f"Summary generation error: {e}")
        ai_summary = ""
        bullet_points = []

    # 读取现有分享数据
    shares_file = Path('data/shares.json')
    shares_file.parent.mkdir(exist_ok=True)

    shares = {}
    if shares_file.exists():
        try:
            with open(shares_file, 'r', encoding='utf-8') as f:
                shares = json.load(f)
        except:
            shares = {}

    # 保存分享数据（包含AI总结）
    shares[share_id] = {
        'news_item': news_item,
        'ai_summary': ai_summary,
        'bullet_points': bullet_points,
        'created_at': dt.now().isoformat(),
        'source': 'Nothing 竞品追踪'
    }

    with open(shares_file, 'w', encoding='utf-8') as f:
        json.dump(shares, f, ensure_ascii=False, indent=2)

    # 生成分享链接
    share_url = request.host_url.rstrip('/') + f'/share/{share_id}'

    return jsonify({
        'share_id': share_id,
        'share_url': share_url
    })


@app.route('/share/<share_id>')
def view_share(share_id):
    """分享页面 - 查看分享的新闻"""
    import json
    from pathlib import Path

    shares_file = Path('data/shares.json')

    if not shares_file.exists():
        return "分享不存在", 404

    try:
        with open(shares_file, 'r', encoding='utf-8') as f:
            shares = json.load(f)
    except:
        return "无法读取分享数据", 500

    share_data = shares.get(share_id)
    if not share_data:
        return "分享不存在或已过期", 404

    return render_template('share.html',
                         news_item=share_data['news_item'],
                         ai_summary=share_data.get('ai_summary', ''),
                         bullet_points=share_data.get('bullet_points', []),
                         share_id=share_id,
                         created_at=share_data.get('created_at'),
                         source=share_data.get('source', 'Nothing 竞品追踪'))


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
