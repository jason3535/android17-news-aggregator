from flask import Flask, render_template
from scraper import load_news

app = Flask(__name__)

@app.route('/preview')
def preview():
    data = load_news()
    return render_template('preview_dynamic.html',
                          news_data=data,
                          news_items=data.get('items', []))

if __name__ == '__main__':
    print('服务启动: http://localhost:5005/preview')
    app.run(port=5005, debug=False)
