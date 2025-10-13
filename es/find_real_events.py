#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
from bs4 import BeautifulSoup
import re

def crawl_page(url):
    """爬取页面内容"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        response.encoding = 'utf-8'
        return response.text
    except Exception as e:
        print(f"爬取页面失败: {e}")
        return None

def find_real_event_names():
    """查找真正的活动名称"""
    url = "https://gamerch.com/ensemble-star-music/895943"
    
    print(f"正在分析页面: {url}")
    html_content = crawl_page(url)
    
    if not html_content:
        print("无法获取页面内容")
        return
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    print("\n=== 查找真正的活动名称 ===")
    
    # 1. 查找所有可能的活动标题格式
    print("\n1. 查找【】格式的活动标题:")
    event_titles = []
    
    # 查找【】格式的标题
    for element in soup.find_all(string=re.compile(r'【[^】]+】')):
        title = element.strip()
        if '【' in title and '】' in title:
            event_titles.append(title)
            print(f"   找到: {title}")
    
    # 2. 查找h标签中的活动标题
    print(f"\n2. 查找标题标签中的活动:")
    for tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
        for h in soup.find_all(tag):
            text = h.get_text(strip=True)
            if '【' in text and '】' in text:
                print(f"   {tag}: {text}")
                event_titles.append(text)
    
    # 3. 查找包含特定关键词的活动
    print(f"\n3. 查找包含活动关键词的文本:")
    activity_keywords = ['スカウト', 'イベント', 'フェス', '鳴動', 'DI:Verse']
    
    for keyword in activity_keywords:
        print(f"\n   关键词: {keyword}")
        for element in soup.find_all(string=re.compile(keyword)):
            text = element.strip()
            if len(text) > 5 and len(text) < 100:  # 合理的长度
                # 检查是否包含【】格式
                if '【' in text and '】' in text:
                    print(f"     找到活动: {text}")
                    event_titles.append(text)
    
    # 4. 分析页面的结构层次
    print(f"\n4. 分析页面结构:")
    
    # 查找所有包含卡面链接的容器
    card_containers = []
    for a in soup.find_all('a', href=True):
        href = a['href']
        text = a.get_text(strip=True)
        
        if ('ensemble-star-music/' in href and 
            re.search(r'/\d+$', href) and 
            text.startswith('［') and '］' in text):
            
            # 找到卡面链接，现在查找它的容器
            container = a.parent
            level = 0
            while container and level < 10:
                container_text = container.get_text("\n", strip=True)
                
                # 查找容器中的活动标题
                event_match = re.search(r'【([^】]+)】', container_text)
                if event_match:
                    event_name = event_match.group(0)
                    print(f"   卡面 '{text[:30]}...' 在容器中找到活动: {event_name}")
                    card_containers.append((text, event_name, level))
                    break
                
                container = container.parent
                level += 1
    
    # 5. 总结发现的活动
    print(f"\n=== 总结 ===")
    unique_events = set(event_titles)
    print(f"发现的活动标题数量: {len(unique_events)}")
    
    for event in sorted(unique_events):
        print(f"  - {event}")
    
    print(f"\n卡面与活动的映射关系:")
    unique_mappings = {}
    for card, event, level in card_containers:
        if event not in unique_mappings:
            unique_mappings[event] = []
        unique_mappings[event].append(card)
    
    for event, cards in unique_mappings.items():
        print(f"\n活动: {event}")
        print(f"  卡面数量: {len(cards)}")
        for card in cards[:3]:  # 只显示前3个
            print(f"    - {card}")
        if len(cards) > 3:
            print(f"    ... 还有 {len(cards) - 3} 个卡面")

if __name__ == "__main__":
    find_real_event_names()