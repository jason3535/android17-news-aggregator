"""
AI 总结模块 - 智能提取新闻核心要点
"""

import re
from typing import Dict, List

def extract_key_sentences(text: str, num_sentences: int = 3) -> str:
    """
    提取文本中的关键句子作为总结
    使用简单但有效的启发式规则
    """
    if not text or not text.strip():
        return ""

    # 清理文本
    text = text.strip()

    # 分割成句子
    sentences = re.split(r'[.!?。！？]\s*', text)
    sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 20]

    if not sentences:
        return text[:200] + "..." if len(text) > 200 else text

    # 如果句子数量少于需要的数量，返回所有句子
    if len(sentences) <= num_sentences:
        return ' '.join(sentences)

    # 评分策略：
    # 1. 前面的句子（特别是第一句）权重更高
    # 2. 包含关键词的句子权重更高
    # 3. 中等长度的句子（不太短也不太长）权重更高

    keywords = [
        'android', 'ios', 'google', 'apple', 'release', 'update', 'feature',
        'beta', 'version', 'developer', 'preview', 'launch', 'announce',
        'new', 'support', 'improve', 'fix', 'bug', 'change', 'add'
    ]

    scored_sentences = []
    for idx, sentence in enumerate(sentences):
        score = 0

        # 位置权重（第一句最重要）
        if idx == 0:
            score += 10
        elif idx == 1:
            score += 5
        elif idx == 2:
            score += 3
        else:
            score += max(0, 5 - idx)

        # 关键词权重
        sentence_lower = sentence.lower()
        keyword_count = sum(1 for kw in keywords if kw in sentence_lower)
        score += keyword_count * 2

        # 长度权重（中等长度最佳）
        word_count = len(sentence.split())
        if 10 <= word_count <= 25:
            score += 3
        elif 8 <= word_count <= 30:
            score += 1

        scored_sentences.append((score, idx, sentence))

    # 按分数排序，但保持原始顺序
    scored_sentences.sort(key=lambda x: x[0], reverse=True)
    selected = scored_sentences[:num_sentences]
    selected.sort(key=lambda x: x[1])  # 按原始顺序

    summary = ' '.join([s[2] for s in selected])
    return summary


def generate_smart_summary(news_item: Dict) -> str:
    """
    生成智能总结
    结合标题和内容，生成简洁的要点
    """
    title = news_item.get('title', '')
    summary = news_item.get('summary', '')

    # 如果有翻译版本，优先使用
    summary_text = news_item.get('summary_translated', summary)

    if not summary_text or len(summary_text.strip()) < 50:
        return title

    # 提取关键句子（2-3句）
    key_points = extract_key_sentences(summary_text, num_sentences=2)

    # 如果提取的内容太短，返回原摘要的前200字符
    if len(key_points) < 50:
        return summary_text[:200] + "..." if len(summary_text) > 200 else summary_text

    return key_points


def generate_bullet_summary(news_item: Dict) -> List[str]:
    """
    生成要点列表（bullet points）
    """
    summary_text = news_item.get('summary_translated') or news_item.get('summary', '')

    if not summary_text:
        return [news_item.get('title', '')]

    # 分割成句子
    sentences = re.split(r'[.!?。！？]\s*', summary_text)
    sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 15]

    # 提取最重要的3个要点
    key_sentences = extract_key_sentences(summary_text, num_sentences=3)
    bullets = re.split(r'[.!?。！？]\s*', key_sentences)
    bullets = [b.strip() for b in bullets if b.strip()]

    # 限制为3个要点
    return bullets[:3]


def generate_one_line_summary(news_item: Dict) -> str:
    """
    生成一句话总结（适合卡片展示）
    """
    title = news_item.get('title', '')
    summary = news_item.get('summary_translated') or news_item.get('summary', '')

    # 提取第一句关键信息
    if summary:
        first_sentence = extract_key_sentences(summary, num_sentences=1)
        if first_sentence and len(first_sentence) < 150:
            return first_sentence

    # 如果没有有效摘要，使用标题
    if len(title) < 100:
        return title
    else:
        return title[:100] + "..."


if __name__ == '__main__':
    # 测试
    test_news = {
        'title': 'Google sets accelerated Android 17 release schedule',
        'summary': 'Besides replacing Developer Previews, the Android 17 Beta cycle is operating on a faster release schedule. Google today announced that Android 17 Beta 2 is now available.',
        'summary_translated': '除了取代开发者预览版之外，Android 17 Beta 周期的发布时间表也更快。谷歌今天宣布 Android 17 Beta 2 现已推出。'
    }

    print("智能总结:")
    print(generate_smart_summary(test_news))
    print("\n要点列表:")
    for bullet in generate_bullet_summary(test_news):
        print(f"• {bullet}")
    print("\n一句话总结:")
    print(generate_one_line_summary(test_news))
