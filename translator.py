"""
翻译模块 - 使用 Google Translate (免费版)
"""

import requests
import json
import re

def translate_text(text: str, target_lang: str = 'zh-CN') -> str:
    """
    翻译文本
    target_lang: 'zh-CN' 中文, 'en' 英文
    """
    if not text or not text.strip():
        return text

    try:
        # 使用 Google Translate 免费 API
        url = "https://translate.googleapis.com/translate_a/single"
        params = {
            'client': 'gtx',
            'sl': 'auto',  # 自动检测源语言
            'tl': target_lang,
            'dt': 't',
            'q': text
        }

        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            result = response.json()
            translated = ''.join([item[0] for item in result[0] if item[0]])
            return translated
    except Exception as e:
        print(f"Translation error: {e}")

    return text


def translate_news_item(item: dict, target_lang: str = 'zh-CN') -> dict:
    """翻译单条新闻"""
    translated = item.copy()

    # 翻译标题和摘要
    if target_lang == 'zh-CN':
        translated['title_translated'] = translate_text(item.get('title', ''), 'zh-CN')
        translated['summary_translated'] = translate_text(item.get('summary', ''), 'zh-CN')
    else:
        # 英文模式，保持原文
        translated['title_translated'] = item.get('title', '')
        translated['summary_translated'] = item.get('summary', '')

    return translated


def translate_news_batch(items: list, target_lang: str = 'zh-CN') -> list:
    """批量翻译新闻"""
    translated_items = []
    for item in items:
        translated_items.append(translate_news_item(item, target_lang))
    return translated_items


if __name__ == '__main__':
    # 测试
    test_text = "Android 17 could take a page from Liquid Glass"
    print(f"Original: {test_text}")
    print(f"Translated: {translate_text(test_text, 'zh-CN')}")
