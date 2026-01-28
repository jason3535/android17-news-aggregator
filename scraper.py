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
from translator import translate_news_batch

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
NEWS_FILE = os.path.join(DATA_DIR, 'news.json')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
}

# Android 17 相关关键词
ANDROID_KEYWORDS = [
    'android 17', 'android17',
    'android baklava',
    'android 16 qpr', 'android16 qpr', 'qpr', 'quarterly platform release',
    'google i/o 2025', 'google i/o 2026',
    'android beta', 'android preview', 'android developer preview',
    'material you', 'gemini android',
    'tensor g5', 'tensor g6',
]

# iOS 27 相关关键词
IOS_KEYWORDS = [
    'ios 27', 'ios27', 'ios 26', 'ios26',
    'ios beta', 'ios preview', 'ios developer',
]

# 合并关键词（用于通用过滤）
KEYWORDS = ANDROID_KEYWORDS + IOS_KEYWORDS

def extract_date_from_url(url: str) -> str:
    """从URL中提取日期（如果URL包含日期模式如/2026/01/28/）"""
    # 匹配 /2026/01/28/ 或 /2025/12/30/ 等格式
    date_patterns = [
        r'/(\d{4})/(\d{1,2})/(\d{1,2})/',  # /2026/01/28/
        r'/(\d{4})-(\d{1,2})-(\d{1,2})/',  # /2026-01-28/
        r'(\d{4})/(\d{1,2})/(\d{1,2})/',   # 2026/01/28
        r'(\d{4})-(\d{1,2})-(\d{1,2})',    # 2026-01-28
    ]

    for pattern in date_patterns:
        match = re.search(pattern, url)
        if match:
            try:
                year, month, day = match.groups()[:3]
                # 确保是有效日期
                year = int(year)
                month = int(month)
                day = int(day)
                if 2000 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31:
                    return f"{year:04d}-{month:02d}-{day:02d}"
            except (ValueError, IndexError):
                continue
    return ""

def parse_news_date(date_str: str, url: str = "") -> str:
    """解析新闻日期，返回格式化的日期字符串

    参数:
        date_str: 原始日期字符串（来自RSS feed等）
        url: 文章URL，用于备用日期提取

    返回:
        格式化的日期字符串：如果有时间部分则返回'YYYY-MM-DD HH:MM'，否则返回'YYYY-MM-DD'
    """
    if not date_str:
        # 尝试从URL提取日期
        if url:
            url_date = extract_date_from_url(url)
            if url_date:
                return url_date
        return ""

    # 尝试多种解析方式
    parsed_date = None

    # 方法1: 使用dateutil.parser
    try:
        parsed_date = date_parser.parse(date_str)
    except:
        pass

    # 方法2: 尝试常见日期格式
    if not parsed_date:
        date_formats = [
            '%Y-%m-%dT%H:%M:%S%z',  # ISO格式带时区
            '%Y-%m-%d %H:%M:%S',    # 简单日期时间
            '%Y-%m-%d',             # 仅日期
            '%a, %d %b %Y %H:%M:%S %z',  # RSS常见格式
            '%a, %d %b %Y %H:%M:%S %Z',  # 带时区名称
        ]

        for fmt in date_formats:
            try:
                parsed_date = datetime.strptime(date_str, fmt)
                break
            except:
                continue

    if parsed_date:
        # 检查是否有非零的时间部分
        if parsed_date.hour == 0 and parsed_date.minute == 0 and parsed_date.second == 0:
            # 只有日期，没有时间
            return parsed_date.strftime('%Y-%m-%d')
        else:
            # 有时间部分
            return parsed_date.strftime('%Y-%m-%d %H:%M')

    # 所有解析都失败，返回原始字符串（截断到合理长度）
    return date_str[:50]

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
    """检查文本是否包含相关关键词"""
    text_lower = text.lower()
    return any(kw in text_lower for kw in KEYWORDS)


def detect_platform(text: str) -> str:
    """检测文本属于哪个平台"""
    text_lower = text.lower()
    is_android = any(kw in text_lower for kw in ANDROID_KEYWORDS)
    is_ios = any(kw in text_lower for kw in IOS_KEYWORDS)

    if is_android and is_ios:
        return 'android'  # 默认 Android
    elif is_ios:
        return 'ios'
    else:
        return 'android'


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

    return image_url


def fetch_og_image(url: str) -> str:
    """从文章页面获取 og:image"""
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            # 尝试 og:image
            og_image = soup.find('meta', property='og:image')
            if og_image and og_image.get('content'):
                return og_image['content']
            # 尝试 twitter:image
            tw_image = soup.find('meta', attrs={'name': 'twitter:image'})
            if tw_image and tw_image.get('content'):
                return tw_image['content']
    except Exception as e:
        print(f"获取 og:image 失败 ({url[:50]}...): {e}")
    return None


def fetch_android_authority() -> list:
    """爬取 Android Authority 的 Android 新闻"""
    news = []
    try:
        # 使用 RSS feed
        feed_url = 'https://www.androidauthority.com/feed/'
        feed = feedparser.parse(feed_url)

        no_match_titles = []
        entries_to_check = feed.entries[:50]  # 检查更多条目
        for entry in entries_to_check:
            title = entry.get('title', '')
            summary = entry.get('summary', '')
            categories = entry.get('tags', [])
            category_text = ' '.join([tag.get('term', '') for tag in categories if isinstance(tag, dict) and 'term' in tag]) if categories else ''

            # 检查标题、摘要和类别是否包含关键词
            if contains_keywords(title) or contains_keywords(summary) or contains_keywords(category_text):
                pub_date = entry.get('published', '')
                date_str = parse_news_date(pub_date, entry.link)

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
                    'platform': 'android',
                    'image': image_url
                })
            else:
                no_match_titles.append(title[:60])

        print(f"Android Authority RSS 处理 {len(entries_to_check)} 条，匹配 {len(news)} 条")
        if no_match_titles and len(news) == 0:
            print(f"  未匹配标题示例: {no_match_titles[:3]}")
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
                date_str = parse_news_date(pub_date, entry.link)

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
                    'platform': detect_platform(title + ' ' + summary),
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
                date_str = parse_news_date(pub_date, entry.link)

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
                    'platform': 'android',
                    'image': image_url
                })
    except Exception as e:
        print(f"Error fetching XDA: {e}")

    return news


def fetch_9to5mac() -> list:
    """爬取 9to5Mac 的 iOS 新闻"""
    news = []
    try:
        feed_url = 'https://9to5mac.com/feed/'
        feed = feedparser.parse(feed_url)

        for entry in feed.entries[:30]:
            title = entry.get('title', '')
            summary = entry.get('summary', '')

            # 检查是否包含 iOS 关键词
            text = (title + ' ' + summary).lower()
            if any(kw in text for kw in IOS_KEYWORDS):
                pub_date = entry.get('published', '')
                date_str = parse_news_date(pub_date, entry.link)

                image_url = extract_image_from_entry(entry)

                news.append({
                    'id': generate_id(entry.link),
                    'title': title,
                    'summary': BeautifulSoup(summary, 'html.parser').get_text()[:300],
                    'url': entry.link,
                    'source': '9to5Mac',
                    'source_icon': '9to5',
                    'date': date_str,
                    'type': 'news',
                    'platform': 'ios',
                    'image': image_url
                })
    except Exception as e:
        print(f"Error fetching 9to5Mac: {e}")

    return news


def fetch_macrumors() -> list:
    """爬取 MacRumors 的 iOS 新闻"""
    news = []
    try:
        feed_url = 'https://feeds.macrumors.com/MacRumors-All'
        feed = feedparser.parse(feed_url)

        for entry in feed.entries[:30]:
            title = entry.get('title', '')
            summary = entry.get('summary', '')

            # 检查是否包含 iOS 关键词
            text = (title + ' ' + summary).lower()
            if any(kw in text for kw in IOS_KEYWORDS):
                pub_date = entry.get('published', '')
                date_str = parse_news_date(pub_date, entry.link)

                image_url = extract_image_from_entry(entry)

                news.append({
                    'id': generate_id(entry.link),
                    'title': title,
                    'summary': BeautifulSoup(summary, 'html.parser').get_text()[:300],
                    'url': entry.link,
                    'source': 'MacRumors',
                    'source_icon': 'MR',
                    'date': date_str,
                    'type': 'news',
                    'platform': 'ios',
                    'image': image_url
                })
    except Exception as e:
        print(f"Error fetching MacRumors: {e}")

    return news


def search_9to5mac(query: str = "ios 27") -> list:
    """通过搜索页面爬取 9to5Mac 的文章"""
    news = []
    try:
        search_url = f"https://9to5mac.com/?s={query.replace(' ', '+')}"
        response = requests.get(search_url, headers=HEADERS, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            articles = soup.find_all('article', limit=20)

            for article in articles:
                try:
                    title_elem = article.find(['h2', 'h3'])
                    if not title_elem:
                        continue
                    link_elem = title_elem.find('a') or article.find('a')
                    if not link_elem:
                        continue

                    title = title_elem.get_text(strip=True)
                    url = link_elem.get('href', '')

                    if not url or not title:
                        continue

                    img = article.find('img')
                    image_url = None
                    if img:
                        image_url = img.get('src') or img.get('data-src') or img.get('data-lazy-src')

                    time_elem = article.find('time')
                    date_str = ''
                    if time_elem and time_elem.get('datetime'):
                        try:
                            parsed_date = date_parser.parse(time_elem['datetime'])
                            date_str = parsed_date.strftime('%Y-%m-%d %H:%M')
                        except:
                            pass

                    # 如果从time元素未提取到日期，尝试从URL提取
                    if not date_str and url:
                        url_date = extract_date_from_url(url)
                        if url_date:
                            date_str = url_date

                    summary_elem = article.find('p')
                    summary = summary_elem.get_text(strip=True)[:300] if summary_elem else ''

                    news.append({
                        'id': generate_id(url),
                        'title': title,
                        'summary': summary,
                        'url': url,
                        'source': '9to5Mac',
                        'source_icon': '9to5',
                        'date': date_str,
                        'type': 'news',
                        'platform': 'ios',
                        'image': image_url
                    })
                except Exception as e:
                    continue

        print(f"9to5Mac 搜索到 {len(news)} 篇文章")
    except Exception as e:
        print(f"搜索 9to5Mac 失败: {e}")

    return news


def search_android_authority(query: str = "android 17") -> list:
    """通过搜索页面爬取 Android Authority 的文章"""
    news = []
    try:
        search_url = f"https://www.androidauthority.com/?s={query.replace(' ', '+')}"
        response = requests.get(search_url, headers=HEADERS, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')

            # 尝试多种选择器查找文章
            articles = []
            selectors = ['article', 'div.post', 'div.entry', 'div.article', 'div.post-item', 'div.news-item']

            for selector in selectors:
                found = soup.select(selector)
                if found:
                    articles = found[:20]  # 限制数量
                    print(f"Android Authority 搜索使用选择器 '{selector}' 找到 {len(found)} 个元素")
                    break

            if not articles:
                print("Android Authority 搜索未找到文章元素")
                return news

            for article in articles:
                try:
                    # 提取标题和链接
                    title_elem = article.find(['h2', 'h3'])
                    if not title_elem:
                        continue
                    link_elem = title_elem.find('a') or article.find('a')
                    if not link_elem:
                        continue

                    title = title_elem.get_text(strip=True)
                    url = link_elem.get('href', '')

                    if not url or not title:
                        continue

                    # 提取图片
                    img = article.find('img')
                    image_url = None
                    if img:
                        image_url = img.get('src') or img.get('data-src') or img.get('data-lazy-src')

                    # 提取日期
                    time_elem = article.find('time')
                    date_str = ''
                    if time_elem and time_elem.get('datetime'):
                        try:
                            parsed_date = date_parser.parse(time_elem['datetime'])
                            date_str = parsed_date.strftime('%Y-%m-%d %H:%M')
                        except:
                            pass

                    # 如果从time元素未提取到日期，尝试从URL提取
                    if not date_str and url:
                        url_date = extract_date_from_url(url)
                        if url_date:
                            date_str = url_date

                    # 提取摘要
                    summary_elem = article.find('p')
                    summary = summary_elem.get_text(strip=True)[:300] if summary_elem else ''

                    news.append({
                        'id': generate_id(url),
                        'title': title,
                        'summary': summary,
                        'url': url,
                        'source': 'Android Authority',
                        'source_icon': 'AA',
                        'date': date_str,
                        'type': 'news',
                        'platform': 'android',
                        'image': image_url
                    })
                except Exception as e:
                    continue

        print(f"Android Authority 搜索到 {len(news)} 篇文章")
    except Exception as e:
        print(f"搜索 Android Authority 失败: {e}")

    return news


def search_9to5google(query: str = "android 17") -> list:
    """通过搜索页面爬取 9to5Google 的文章"""
    news = []
    try:
        search_url = f"https://9to5google.com/?s={query.replace(' ', '+')}"
        response = requests.get(search_url, headers=HEADERS, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            articles = soup.find_all('article', limit=20)

            for article in articles:
                try:
                    # 提取标题和链接
                    title_elem = article.find(['h2', 'h3'])
                    if not title_elem:
                        continue
                    link_elem = title_elem.find('a') or article.find('a')
                    if not link_elem:
                        continue

                    title = title_elem.get_text(strip=True)
                    url = link_elem.get('href', '')

                    if not url or not title:
                        continue

                    # 提取图片
                    img = article.find('img')
                    image_url = None
                    if img:
                        image_url = img.get('src') or img.get('data-src') or img.get('data-lazy-src')

                    # 提取日期
                    time_elem = article.find('time')
                    date_str = ''
                    if time_elem and time_elem.get('datetime'):
                        try:
                            parsed_date = date_parser.parse(time_elem['datetime'])
                            date_str = parsed_date.strftime('%Y-%m-%d %H:%M')
                        except:
                            pass

                    # 如果从time元素未提取到日期，尝试从URL提取
                    if not date_str and url:
                        url_date = extract_date_from_url(url)
                        if url_date:
                            date_str = url_date

                    # 提取摘要
                    summary_elem = article.find('p')
                    summary = summary_elem.get_text(strip=True)[:300] if summary_elem else ''

                    news.append({
                        'id': generate_id(url),
                        'title': title,
                        'summary': summary,
                        'url': url,
                        'source': '9to5Google',
                        'source_icon': '9to5',
                        'date': date_str,
                        'type': 'news',
                        'platform': detect_platform(title + ' ' + summary),
                        'image': image_url
                    })
                except Exception as e:
                    continue

        print(f"9to5Google 搜索到 {len(news)} 篇文章")
    except Exception as e:
        print(f"搜索 9to5Google 失败: {e}")

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
    """爬取所有来源的新闻，保留历史数据"""

    # 1. 加载历史数据
    existing_data = load_news()
    existing_news = {item['id']: item for item in existing_data.get('items', []) if item['type'] == 'news'}
    print(f"已有历史新闻: {len(existing_news)} 条")

    # 2. 爬取新数据（RSS + 搜索）
    new_news = []

    # RSS feeds
    print("爬取 RSS feeds...")
    new_news.extend(fetch_android_authority())
    new_news.extend(fetch_9to5google())
    new_news.extend(fetch_xda_developers())

    # iOS RSS feeds
    print("爬取 iOS RSS feeds...")
    new_news.extend(fetch_9to5mac())
    new_news.extend(fetch_macrumors())

    # 搜索页面（获取更多历史文章）
    print("搜索 Android 历史文章...")
    new_news.extend(search_android_authority("android 17"))
    new_news.extend(search_9to5google("android 17"))
    new_news.extend(search_android_authority("android 17 beta"))
    new_news.extend(search_9to5google("android 17 beta"))
    new_news.extend(search_android_authority("android 17 preview"))
    new_news.extend(search_9to5google("android 17 preview"))
    new_news.extend(search_android_authority("android baklava"))
    new_news.extend(search_9to5google("android baklava"))
    new_news.extend(search_android_authority("android 16 qpr"))
    new_news.extend(search_9to5google("android 16 qpr"))
    new_news.extend(search_android_authority("qpr"))
    new_news.extend(search_9to5google("qpr"))

    # iOS 搜索
    print("搜索 iOS 历史文章...")
    new_news.extend(search_9to5mac("ios 27"))
    new_news.extend(search_9to5mac("iphone 17"))

    # 3. 合并新旧数据（去重，以 id 为准）
    new_count = 0
    for item in new_news:
        if item['id'] not in existing_news:
            existing_news[item['id']] = item
            new_count += 1

    print(f"新增新闻: {new_count} 条")

    # 4. 转换回列表并排序
    news_items = list(existing_news.values())
    try:
        news_items.sort(key=lambda x: x['date'], reverse=True)
    except:
        pass

    # 4.5 补充缺失的图片（从文章页面获取 og:image）
    print("补充缺失图片...")
    for item in news_items:
        if not item.get('image') and item.get('url'):
            image = fetch_og_image(item['url'])
            if image:
                item['image'] = image
                print(f"  获取图片: {item['title'][:40]}...")

    # 4.6 严格过滤 Android 17 新闻（清理非 Android 17 内容）
    print("严格过滤 Android 17 新闻...")
    # 保留的关键词：Android 17 和相关版本
    keep_keywords = ['android 17', 'android17', 'android baklava', 'android 16 qpr', 'qpr', 'quarterly platform release']
    # 需要过滤的单纯硬件关键词（如果没有版本关键词）
    hardware_keywords = ['pixel 10', 'pixel 11', 'pixel 10a', 'pixel10', 'pixel11']

    filtered_items = []
    for item in news_items:
        if item.get('type') == 'news' and item.get('platform') == 'android':
            text = (item.get('title', '') + ' ' + item.get('summary', '')).lower()

            # 检查是否包含要保留的 Android 版本关键词
            has_version = any(kw in text for kw in keep_keywords)
            # 检查是否只包含硬件关键词
            has_hardware = any(kw in text for kw in hardware_keywords)

            if has_version:
                # 包含 Android 版本关键词，保留
                filtered_items.append(item)
            elif has_hardware:
                # 只包含硬件关键词（如 Pixel），没有版本关键词，过滤掉
                print(f"  移除单纯硬件新闻: {item.get('title', '')[:50]}...")
            else:
                # 既没有版本关键词也没有硬件关键词，可能是其他 Android 新闻，过滤掉
                print(f"  移除非 Android 17 新闻: {item.get('title', '')[:50]}...")
        else:
            filtered_items.append(item)  # 保留 iOS 新闻和爆料人士
    news_items = filtered_items

    # 4.7 严格过滤 iOS 新闻（清理非 iOS 27/26 beta 内容）
    print("严格过滤 iOS 新闻...")
    # 保留的关键词：iOS 版本相关
    ios_keep_keywords = ['ios 27', 'ios27', 'ios 26', 'ios26', 'ios beta', 'ios preview', 'ios developer']
    # 需要过滤的硬件关键词（如果没有版本关键词）
    ios_hardware_keywords = ['iphone 17', 'iphone17', 'iphone 18']

    ios_filtered_items = []
    for item in news_items:
        if item.get('type') == 'news' and item.get('platform') == 'ios':
            text = (item.get('title', '') + ' ' + item.get('summary', '')).lower()

            # 检查是否包含要保留的 iOS 版本关键词
            has_ios_version = any(kw in text for kw in ios_keep_keywords)
            # 检查是否包含硬件关键词
            has_ios_hardware = any(kw in text for kw in ios_hardware_keywords)

            if has_ios_version:
                # 包含 iOS 版本关键词，保留
                ios_filtered_items.append(item)
            elif has_ios_hardware:
                # 只包含硬件关键词（如 iPhone），没有版本关键词，过滤掉
                print(f"  移除单纯 iPhone 硬件新闻: {item.get('title', '')[:50]}...")
            else:
                # 既没有版本关键词也没有硬件关键词，可能是其他 iOS 新闻，过滤掉
                print(f"  移除非 iOS 27/26 beta 新闻: {item.get('title', '')[:50]}...")
        else:
            ios_filtered_items.append(item)  # 保留 Android 新闻和爆料人士
    news_items = ios_filtered_items

    # 5. 添加爆料人士信息（每次更新）
    leaker_items = get_leaker_info()

    # 6. 合并结果
    sorted_news = news_items + leaker_items

    # 7. 为新增新闻项添加中文翻译
    print("开始预翻译中文内容...")
    try:
        # 只翻译没有翻译过的新闻
        news_to_translate = [item for item in news_items if not item.get('title_translated')]
        if news_to_translate:
            print(f"需要翻译: {len(news_to_translate)} 条")
            translated_news = translate_news_batch(news_to_translate, 'zh-CN')
            # 更新翻译字段
            for i, item in enumerate(news_to_translate):
                item.update(translated_news[i])
    except Exception as e:
        print(f"预翻译失败，将继续使用实时翻译: {e}")

    # 统计各平台数量
    android_count = len([item for item in news_items if item.get('platform') == 'android'])
    ios_count = len([item for item in news_items if item.get('platform') == 'ios'])

    result = {
        'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'total_count': len(sorted_news),
        'news_count': len(news_items),
        'android_count': android_count,
        'ios_count': ios_count,
        'leaker_count': len(leaker_items),
        'items': sorted_news
    }

    # 8. 保存到文件
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
