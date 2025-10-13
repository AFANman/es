#!/usr/bin/env python3
"""
从全年活动目录页面直接提取卡面详情链接
"""

import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin
from datetime import datetime
import calendar

def get_month_end_day(month, year=2025):
    """获取指定月份的最后一天"""
    return calendar.monthrange(year, month)[1]

def is_target_date(date_str):
    """判断是否为目标日期：10日、14日、15日、25日、月末前一天、月末"""
    match = re.search(r'(\d{2})月(\d{2})日', date_str)
    if not match:
        return False
    
    month = int(match.group(1))
    day = int(match.group(2))
    
    # 目标日期
    target_days = [10, 14, 15, 25]
    
    if day in target_days:
        return True
    
    # 检查是否为月末或月末前一天
    month_end = get_month_end_day(month)
    if day == month_end or day == month_end - 1:
        return True
    
    return False

def extract_card_links_from_directory():
    """从目录页面提取卡面详情链接"""
    url = 'https://gamerch.com/ensemble-star-music/895943'
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    try:
        print(f"正在分析目录页面: {url}")
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 查找所有可能的卡面链接
        all_links = soup.find_all('a', href=True)
        
        # 过滤出卡面详情链接（通常包含entry/数字的模式）
        card_links = []
        for link in all_links:
            href = link['href']
            text = link.get_text(strip=True)
            
            # 卡面链接通常是 /entry/数字 的格式
            if re.search(r'/entry/\d+$', href) and 'gamerch.com' in href:
                card_links.append({
                    'text': text,
                    'url': href,
                    'link_element': link
                })
        
        print(f"找到 {len(card_links)} 个可能的卡面链接")
        
        # 分析每个链接的上下文，查找日期信息
        target_card_links = []
        
        for card_link in card_links:
            link_element = card_link['link_element']
            
            # 向上查找包含日期的父元素
            current = link_element
            date_context = ""
            
            for _ in range(5):  # 最多向上查找5层
                if current:
                    text = current.get_text()
                    # 查找日期模式
                    date_matches = re.findall(r'\d{2}月\d{2}日', text)
                    if date_matches:
                        date_context = date_matches[0]  # 取第一个匹配的日期
                        break
                    current = current.parent
                else:
                    break
            
            # 如果找到日期上下文，检查是否为目标日期
            if date_context and is_target_date(date_context):
                target_card_links.append({
                    'date': date_context,
                    'text': card_link['text'],
                    'url': card_link['url']
                })
        
        print(f"\n找到 {len(target_card_links)} 个目标日期的卡面链接:")
        
        # 按日期分组显示
        date_groups = {}
        for card in target_card_links:
            date = card['date']
            if date not in date_groups:
                date_groups[date] = []
            date_groups[date].append(card)
        
        for date in sorted(date_groups.keys()):
            cards = date_groups[date]
            print(f"\n{date} ({len(cards)}个卡面):")
            for i, card in enumerate(cards):
                print(f"  {i+1}. {card['text']}")
                print(f"     URL: {card['url']}")
        
        return target_card_links
        
    except Exception as e:
        print(f"错误: {e}")
        return []

def extract_card_links_alternative():
    """备选方案：通过页面内容结构分析提取卡面链接"""
    url = 'https://gamerch.com/ensemble-star-music/895943'
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    try:
        print(f"\n使用备选方案分析页面...")
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 查找包含卡面信息的区域
        # 通常卡面会以特定格式出现，如 ☆5［卡面名称］角色名
        card_pattern = r'☆[345]［[^］]+］[^☆\n]+'
        
        page_text = soup.get_text()
        card_matches = re.finditer(card_pattern, page_text)
        
        found_cards = []
        for match in card_matches:
            card_text = match.group()
            start_pos = match.start()
            
            # 在卡面文本前后查找日期
            context_start = max(0, start_pos - 200)
            context_end = min(len(page_text), start_pos + 200)
            context = page_text[context_start:context_end]
            
            # 查找日期
            date_matches = re.findall(r'\d{2}月\d{2}日', context)
            if date_matches:
                for date in date_matches:
                    if is_target_date(date):
                        found_cards.append({
                            'date': date,
                            'card': card_text,
                            'context': context
                        })
                        break
        
        print(f"通过文本分析找到 {len(found_cards)} 个目标卡面:")
        for i, card in enumerate(found_cards[:10]):  # 只显示前10个
            print(f"{i+1}. {card['date']}: {card['card']}")
        
        return found_cards
        
    except Exception as e:
        print(f"备选方案错误: {e}")
        return []

if __name__ == "__main__":
    print("=" * 60)
    print("方案1: 直接提取卡面链接")
    print("=" * 60)
    card_links = extract_card_links_from_directory()
    
    print("\n" + "=" * 60)
    print("方案2: 文本分析提取卡面信息")
    print("=" * 60)
    card_info = extract_card_links_alternative()
    
    print(f"\n总结:")
    print(f"方案1找到 {len(card_links)} 个卡面链接")
    print(f"方案2找到 {len(card_info)} 个卡面信息")