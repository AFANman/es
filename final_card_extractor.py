#!/usr/bin/env python3
"""
最终的卡面提取脚本 - 从全年活动目录页面提取目标日期的卡面链接
"""

import requests
from bs4 import BeautifulSoup
import re
import calendar
from urllib.parse import urljoin

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

def extract_target_cards():
    """提取目标日期的卡面信息"""
    url = 'https://gamerch.com/ensemble-star-music/895943'
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    try:
        print(f"正在分析页面: {url}")
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 获取页面文本并按行分割
        page_text = soup.get_text()
        lines = page_text.split('\n')
        
        target_cards = []
        
        # 逐行分析，查找目标日期和相关的卡面信息
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            
            # 查找包含日期的行
            dates = re.findall(r'\d{2}月\d{2}日', line)
            
            for date in dates:
                if is_target_date(date):
                    print(f"\n找到目标日期: {date}")
                    print(f"  行 {i}: {line}")
                    
                    # 在当前行和前后几行中查找卡面信息
                    search_range = 10  # 前后10行
                    start_line = max(0, i - search_range)
                    end_line = min(len(lines), i + search_range + 1)
                    
                    context_lines = lines[start_line:end_line]
                    context_text = '\n'.join(context_lines)
                    
                    # 查找卡面
                    cards = re.findall(r'☆[345]［[^］]+］[^☆\n]*', context_text)
                    
                    if cards:
                        print(f"  找到 {len(cards)} 个卡面:")
                        for card in cards:
                            card = card.strip()
                            print(f"    - {card}")
                            
                            # 提取卡面名称和角色
                            card_match = re.search(r'☆([345])［([^］]+)］(.+)', card)
                            if card_match:
                                star_level = card_match.group(1)
                                card_name = card_match.group(2)
                                character = card_match.group(3).strip()
                                
                                target_cards.append({
                                    'date': date,
                                    'star_level': star_level,
                                    'card_name': card_name,
                                    'character': character,
                                    'full_text': card,
                                    'context_line': i
                                })
                    else:
                        print(f"  在附近未找到卡面信息")
        
        # 去重
        unique_cards = []
        seen = set()
        
        for card in target_cards:
            key = (card['date'], card['full_text'])
            if key not in seen:
                seen.add(key)
                unique_cards.append(card)
        
        print(f"\n总结: 找到 {len(unique_cards)} 个目标日期的唯一卡面")
        
        # 按日期分组显示
        date_groups = {}
        for card in unique_cards:
            date = card['date']
            if date not in date_groups:
                date_groups[date] = []
            date_groups[date].append(card)
        
        print(f"\n按日期分组的结果:")
        for date in sorted(date_groups.keys()):
            cards = date_groups[date]
            print(f"\n{date} ({len(cards)}个卡面):")
            for i, card in enumerate(cards):
                print(f"  {i+1}. ☆{card['star_level']}［{card['card_name']}］{card['character']}")
        
        return unique_cards
        
    except Exception as e:
        print(f"错误: {e}")
        return []

def find_card_detail_links(target_cards):
    """查找卡面的详情链接"""
    if not target_cards:
        print("没有目标卡面，跳过链接查找")
        return []
    
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
        
        for card in target_cards:
            card_name = card['card_name']
            character = card['character']
            
            print(f"\n查找卡面链接: ☆{card['star_level']}［{card_name}］{character}")
            
            found_link = False
            
            # 在所有链接中查找匹配的
            for link in all_links:
                link_text = link.get_text(strip=True)
                href = link['href']
                
                # 检查是否为entry链接且包含相关信息
                if '/entry/' in href and href.startswith('https://gamerch.com'):
                    # 检查链接文本是否包含卡面名称或角色名
                    if (card_name in link_text or character in link_text or 
                        any(word in link_text for word in card_name.split()) or
                        any(word in link_text for word in character.split())):
                        
                        cards_with_links.append({
                            'date': card['date'],
                            'star_level': card['star_level'],
                            'card_name': card_name,
                            'character': character,
                            'full_text': card['full_text'],
                            'link_text': link_text,
                            'url': href
                        })
                        
                        print(f"  找到链接: {link_text}")
                        print(f"  URL: {href}")
                        found_link = True
                        break
            
            if not found_link:
                print(f"  未找到对应链接")
        
        print(f"\n最终找到 {len(cards_with_links)} 个卡面的详情链接")
        return cards_with_links
        
    except Exception as e:
        print(f"链接查找错误: {e}")
        return []

def generate_crawl_urls(cards_with_links):
    """生成用于爬取的URL列表"""
    if not cards_with_links:
        print("没有找到卡面链接")
        return []
    
    crawl_urls = []
    
    print(f"\n生成爬取URL列表:")
    for i, card in enumerate(cards_with_links):
        crawl_urls.append({
            'url': card['url'],
            'date': card['date'],
            'card_info': f"☆{card['star_level']}［{card['card_name']}］{card['character']}"
        })
        
        print(f"{i+1}. {card['date']}: {card['card_info']}")
        print(f"   URL: {card['url']}")
    
    return crawl_urls

if __name__ == "__main__":
    print("=" * 80)
    print("从全年活动目录页面提取目标日期的卡面信息")
    print("目标日期: 10日、14日、15日、25日、月末前一天、月末")
    print("=" * 80)
    
    # 步骤1: 提取目标卡面
    target_cards = extract_target_cards()
    
    if target_cards:
        # 步骤2: 查找详情链接
        cards_with_links = find_card_detail_links(target_cards)
        
        if cards_with_links:
            # 步骤3: 生成爬取URL
            crawl_urls = generate_crawl_urls(cards_with_links)
            
            print(f"\n" + "=" * 80)
            print(f"提取完成！共找到 {len(crawl_urls)} 个目标卡面的详情链接")
            print("=" * 80)
        else:
            print("\n未找到任何卡面的详情链接")
    else:
        print("\n未找到任何目标日期的卡面")