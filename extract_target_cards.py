#!/usr/bin/env python3
"""
从全年活动目录页面精确提取目标日期的卡面信息
"""

import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin
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

def extract_cards_from_content():
    """从页面内容中提取卡面信息"""
    url = 'https://gamerch.com/ensemble-star-music/895943'
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    try:
        print(f"正在分析页面: {url}")
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 查找包含日期和卡面信息的div
        content_divs = soup.find_all('div', class_=True)
        target_divs = []
        
        for div in content_divs:
            text = div.get_text()
            if re.search(r'\d{2}月\d{2}日', text) and re.search(r'☆[345]', text):
                target_divs.append(div)
        
        print(f"找到 {len(target_divs)} 个包含日期和卡面信息的区域")
        
        # 提取每个区域的详细信息
        all_cards = []
        
        for i, div in enumerate(target_divs):
            print(f"\n分析区域 {i+1}:")
            text = div.get_text()
            
            # 查找所有日期
            dates = re.findall(r'\d{2}月\d{2}日', text)
            print(f"  找到日期: {dates}")
            
            # 查找所有卡面
            cards = re.findall(r'☆[345]［[^］]+］[^☆\n]*', text)
            print(f"  找到卡面: {len(cards)} 个")
            
            # 尝试关联日期和卡面
            for date in dates:
                if is_target_date(date):
                    print(f"  目标日期: {date}")
                    
                    # 查找该日期附近的卡面
                    date_pos = text.find(date)
                    if date_pos != -1:
                        # 在日期前后500字符范围内查找卡面
                        start = max(0, date_pos - 500)
                        end = min(len(text), date_pos + 500)
                        context = text[start:end]
                        
                        context_cards = re.findall(r'☆[345]［[^］]+］[^☆\n]*', context)
                        
                        for card in context_cards:
                            all_cards.append({
                                'date': date,
                                'card': card.strip(),
                                'context': context[:100] + "..."
                            })
                            print(f"    - {card.strip()}")
        
        # 去重并按日期排序
        unique_cards = []
        seen = set()
        
        for card_info in all_cards:
            key = (card_info['date'], card_info['card'])
            if key not in seen:
                seen.add(key)
                unique_cards.append(card_info)
        
        # 按日期排序
        unique_cards.sort(key=lambda x: x['date'])
        
        print(f"\n总结: 找到 {len(unique_cards)} 个目标日期的唯一卡面")
        
        # 按日期分组显示
        date_groups = {}
        for card in unique_cards:
            date = card['date']
            if date not in date_groups:
                date_groups[date] = []
            date_groups[date].append(card)
        
        for date in sorted(date_groups.keys()):
            cards = date_groups[date]
            print(f"\n{date} ({len(cards)}个卡面):")
            for i, card in enumerate(cards):
                print(f"  {i+1}. {card['card']}")
        
        return unique_cards
        
    except Exception as e:
        print(f"错误: {e}")
        return []

def extract_cards_from_tables():
    """从表格中提取卡面信息"""
    url = 'https://gamerch.com/ensemble-star-music/895943'
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    try:
        print(f"\n从表格中提取卡面信息...")
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        tables = soup.find_all('table')
        print(f"找到 {len(tables)} 个表格")
        
        all_cards = []
        
        for i, table in enumerate(tables):
            print(f"\n分析表格 {i+1}:")
            rows = table.find_all('tr')
            
            for j, row in enumerate(rows):
                cells = row.find_all(['td', 'th'])
                row_text = ' '.join([cell.get_text(strip=True) for cell in cells])
                
                # 查找日期
                dates = re.findall(r'\d{2}月\d{2}日', row_text)
                # 查找卡面
                cards = re.findall(r'☆[345]［[^］]+］[^☆\n]*', row_text)
                
                if dates and cards:
                    print(f"  行 {j+1}: 日期={dates}, 卡面={len(cards)}个")
                    
                    for date in dates:
                        if is_target_date(date):
                            for card in cards:
                                all_cards.append({
                                    'date': date,
                                    'card': card.strip(),
                                    'source': f'表格{i+1}行{j+1}'
                                })
                                print(f"    目标: {date} - {card.strip()}")
        
        print(f"\n从表格中找到 {len(all_cards)} 个目标卡面")
        return all_cards
        
    except Exception as e:
        print(f"表格提取错误: {e}")
        return []

def find_card_detail_links(cards_info):
    """查找卡面的详情链接"""
    url = 'https://gamerch.com/ensemble-star-music/895943'
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    try:
        print(f"\n查找卡面详情链接...")
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 获取所有链接
        all_links = soup.find_all('a', href=True)
        
        cards_with_links = []
        
        for card_info in cards_info:
            card_name = card_info['card']
            
            # 提取卡面名称的关键词
            card_match = re.search(r'☆[345]［([^］]+)］(.+)', card_name)
            if card_match:
                card_title = card_match.group(1)
                character = card_match.group(2).strip()
                
                print(f"查找卡面: {card_title} - {character}")
                
                # 在所有链接中查找匹配的
                for link in all_links:
                    link_text = link.get_text(strip=True)
                    href = link['href']
                    
                    # 检查链接文本是否包含卡面名称或角色名
                    if (card_title in link_text or character in link_text) and '/entry/' in href:
                        cards_with_links.append({
                            'date': card_info['date'],
                            'card': card_name,
                            'link_text': link_text,
                            'url': href
                        })
                        print(f"  找到链接: {link_text} -> {href}")
                        break
        
        print(f"\n找到 {len(cards_with_links)} 个卡面的详情链接")
        return cards_with_links
        
    except Exception as e:
        print(f"链接查找错误: {e}")
        return []

if __name__ == "__main__":
    print("=" * 60)
    print("方案1: 从内容区域提取卡面")
    print("=" * 60)
    content_cards = extract_cards_from_content()
    
    print("\n" + "=" * 60)
    print("方案2: 从表格提取卡面")
    print("=" * 60)
    table_cards = extract_cards_from_tables()
    
    # 合并结果
    all_cards = content_cards + table_cards
    
    if all_cards:
        print("\n" + "=" * 60)
        print("查找卡面详情链接")
        print("=" * 60)
        cards_with_links = find_card_detail_links(all_cards)
        
        if cards_with_links:
            print(f"\n最终结果: 找到 {len(cards_with_links)} 个目标卡面的详情链接")
            for i, card in enumerate(cards_with_links):
                print(f"{i+1}. {card['date']}: {card['card']}")
                print(f"   链接: {card['url']}")
    else:
        print("\n未找到任何目标卡面")