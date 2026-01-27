"""
Android 17 News Scraper
爬取 Android Authority, 9to5Google 以及著名爆料人士的 Android 17 相关新闻
"""

import requests
from bs4 import BeautifulSoup
import feedparser
import json
import os
from datetime import datetime
from dateutil import parser as date_parser
import re
import hashlib

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
NEWS_FILE = os.path.join(DATA_DIR, 'news.json')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
}

# Android 17 相关关键词
KEYWORDS = [
    'android 17', 'android17', 'android 16', 'android 2025', 'android 2026',
    'pixel 10', 'pixel 11', 'android baklava', 'android dessert',
    'google i/o 2025', 'google i/o 2026', 'android beta', 'android preview'
]

# 著名爆料人士 Twitter/X 账号
LEAKERS = [
    {'name': 'OnLeaks', 'handle': '@OnLeaks', 'avatar': 'https://pbs.twimg.com/profile_images/1590049827662032896/3Jdz7fGM_400x400.jpg'},
    {'name': 'Evan Blass', 'handle': '@evleaks', 'avatar': 'https://pbs.twimg.com/profile_images/1683602571156635648/NmFNPE3__400x400.jpg'},
    {'name': 'Ice Universe', 'handle': '@UniverseIce', 'avatar': 'https://pbs.twimg.com/profile_images/1590753781534375937/G63Fcoiq_400x400.jpg'},
    {'name': 'Mishaal Rahman', 'handle': '@MishaalRahman', 'avatar': 'https://pbs.twimg.com/profile_images/1772892077495795712/nnAPEaB2_400x400.jpg'},
    {'name': 'Max Weinbach', 'handle': '@MaxWineworthy', 'avatar': 'https://pbs.twimg.com/profile_images/1402848727407013888/6VrpdaKh_400x400.jpg'},
]


def generate_id(url: str) -> str:
    """生成新闻唯一ID"""
    return hashlib.md5(url.encode()).hexdigest()[:12]


def contains_keywords(text: str) -> bool:
    """检查文本是否包含 Android 17 相关关键词"""
    text_lower = text.lower()
    return any(kw in text_lower for kw in KEYWORDS)


def extract_image_from_entry(entry) -> str:
    """从 RSS entry 中提取图片 URL"""
    image_url = None

    # 1. 尝试从 media_content 获取
    if hasattr(entry, 'media_content') and entry.media_content:
        for media in entry.media_content:
            if media.get('medium') == 'image' or media.get('type', '').startswith('image'):
                image_url = media.get('url')
                if image_url:
                    break

    # 2. 尝试从 media_thumbnail 获取
    if not image_url and hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
        image_url = entry.media_thumbnail[0].get('url')

    # 3. 尝试从 enclosure 获取
    if not image_url and hasattr(entry, 'enclosures') and entry.enclosures:
        for enc in entry.enclosures:
            if enc.get('type', '').startswith('image'):
                image_url = enc.get('href') or enc.get('url')
                if image_url:
                    break

    # 4. 尝试从 content 或 summary 中的 <img> 标签获取
    if not image_url:
        content = ''
        if hasattr(entry, 'content') and entry.content:
            content = entry.content[0].get('value', '')
        elif hasattr(entry, 'summary'):
            content = entry.summary

        if content:
            soup = BeautifulSoup(content, 'html.parser')
            img_tag = soup.find('img')
            if img_tag:
                image_url = img_tag.get('src') or img_tag.get('data-src')

    # 5. 尝试从 link 的 og:image 获取（备用，较慢）
    # 暂不启用，因为会增加请求时间

    return image_url


def fetch_android_authority() -> list:
    """爬取 Android Authority 的 Android 新闻"""
    news = []
    try:
        # 使用 RSS feed
        feed_url = 'https://www.androidauthority.com/feed/'
        feed = feedparser.parse(feed_url)

        for entry in feed.entries[:30]:
            title = entry.get('title', '')
            summary = entry.get('summary', '')

            if contains_keywords(title) or contains_keywords(summary):
                pub_date = entry.get('published', '')
                try:
                    parsed_date = date_parser.parse(pub_date)
                    date_str = parsed_date.strftime('%Y-%m-%d %H:%M')
                except:
                    date_str = pub_date

                # 提取图片
                image_url = extract_image_from_entry(entry)

                news.append({
                    'id': generate_id(entry.link),
                    'title': title,
                    'summary': BeautifulSoup(summary, 'html.parser').get_text()[:300],
                    'url': entry.link,
                    'source': 'Android Authority',
                    'source_icon': 'AA',
                    'date': date_str,
                    'type': 'news',
                    'image': image_url
                })
    except Exception as e:
        print(f"Error fetching Android Authority: {e}")

    return news


def fetch_9to5google() -> list:
    """爬取 9to5Google 的 Android 新闻"""
    news = []
    try:
        feed_url = 'https://9to5google.com/feed/'
        feed = feedparser.parse(feed_url)

        for entry in feed.entries[:30]:
            title = entry.get('title', '')
            summary = entry.get('summary', '')

            if contains_keywords(title) or contains_keywords(summary):
                pub_date = entry.get('published', '')
                try:
                    parsed_date = date_parser.parse(pub_date)
                    date_str = parsed_date.strftime('%Y-%m-%d %H:%M')
                except:
                    date_str = pub_date

                # 提取图片
                image_url = extract_image_from_entry(entry)

                news.append({
                    'id': generate_id(entry.link),
                    'title': title,
                    'summary': BeautifulSoup(summary, 'html.parser').get_text()[:300],
                    'url': entry.link,
                    'source': '9to5Google',
                    'source_icon': '9to5',
                    'date': date_str,
                    'type': 'news',
                    'image': image_url
                })
    except Exception as e:
        print(f"Error fetching 9to5Google: {e}")

    return news


def fetch_xda_developers() -> list:
    """爬取 XDA Developers 的 Android 新闻"""
    news = []
    try:
        feed_url = 'https://www.xda-developers.com/feed/'
        feed = feedparser.parse(feed_url)

        for entry in feed.entries[:30]:
            title = entry.get('title', '')
            summary = entry.get('summary', '')

            if contains_keywords(title) or contains_keywords(summary):
                pub_date = entry.get('published', '')
                try:
                    parsed_date = date_parser.parse(pub_date)
                    date_str = parsed_date.strftime('%Y-%m-%d %H:%M')
                except:
                    date_str = pub_date

                # 提取图片
                image_url = extract_image_from_entry(entry)

                news.append({
                    'id': generate_id(entry.link),
                    'title': title,
                    'summary': BeautifulSoup(summary, 'html.parser').get_text()[:300],
                    'url': entry.link,
                    'source': 'XDA Developers',
                    'source_icon': 'XDA',
                    'date': date_str,
                    'type': 'news',
                    'image': image_url
                })
    except Exception as e:
        print(f"Error fetching XDA: {e}")

    return news


def get_leaker_info() -> list:
    """返回著名爆料人士信息（供前端显示）"""
    return [
        {
            'id': f'leaker_{i}',
            'title': f"{leaker['name']} ({leaker['handle']})",
            'summary': f"关注 {leaker['handle']} 获取最新 Android 爆料信息。由于 Twitter/X API 限制，请手动查看其账号获取最新消息。",
            'url': f"https://twitter.com/{leaker['handle'].replace('@', '')}",
            'source': 'Leaker',
            'source_icon': '🔥',
            'date': datetime.now().strftime('%Y-%m-%d'),
            'type': 'leaker',
            'image': leaker.get('avatar')
        }
        for i, leaker in enumerate(LEAKERS)
    ]


def scrape_all() -> dict:
    """爬取所有来源的新闻"""
    all_news = []

    # 爬取各个来源
    all_news.extend(fetch_android_authority())
    all_news.extend(fetch_9to5google())
    all_news.extend(fetch_xda_developers())

    # 添加爆料人士信息
    all_news.extend(get_leaker_info())

    # 按日期排序（新闻类型）
    news_items = [n for n in all_news if n['type'] == 'news']
    leaker_items = [n for n in all_news if n['type'] == 'leaker']

    # 对新闻按日期排序
    try:
        news_items.sort(key=lambda x: x['date'], reverse=True)
    except:
        pass

    # 合并结果
    sorted_news = news_items + leaker_items

    result = {
        'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'total_count': len(sorted_news),
        'news_count': len(news_items),
        'leaker_count': len(leaker_items),
        'items': sorted_news
    }

    # 保存到文件
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(NEWS_FILE, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return result


def load_news() -> dict:
    """加载已保存的新闻数据"""
    if os.path.exists(NEWS_FILE):
        with open(NEWS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'items': [], 'last_updated': None, 'total_count': 0}


if __name__ == '__main__':
    print("开始爬取 Android 17 新闻...")
    result = scrape_all()
    print(f"完成！共获取 {result['total_count']} 条内容")
    print(f"其中新闻 {result['news_count']} 条，爆料人士 {result['leaker_count']} 位")
