#!/usr/bin/env python3
"""
从页面排行榜区域提取卡面信息，并关联到目标日期
"""

import requests
from bs4 import BeautifulSoup
import re
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

def extract_cards_and_dates():
    """提取卡面信息和日期信息"""
    url = 'https://gamerch.com/ensemble-star-music/895943'
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    try:
        print(f"正在分析页面: {url}")
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 获取页面文本
        page_text = soup.get_text()
        
        # 1. 提取所有卡面信息
        print("1. 提取所有卡面信息:")
        all_cards = re.findall(r'☆[345]［[^］]+］[^☆\n]*', page_text)
        print(f"   找到 {len(all_cards)} 个卡面")
        
        # 解析卡面信息
        parsed_cards = []
        for card in all_cards:
            card = card.strip()
            card_match = re.search(r'☆([345])［([^］]+)］(.+)', card)
            if card_match:
                star_level = card_match.group(1)
                card_name = card_match.group(2)
                character = card_match.group(3).strip()
                
                parsed_cards.append({
                    'star_level': star_level,
                    'card_name': card_name,
                    'character': character,
                    'full_text': card
                })
        
        print(f"   成功解析 {len(parsed_cards)} 个卡面")
        
        # 显示前10个卡面
        for i, card in enumerate(parsed_cards[:10]):
            print(f"     {i+1}. ☆{card['star_level']}［{card['card_name']}］{card['character']}")
        
        # 2. 提取所有目标日期
        print(f"\n2. 提取目标日期:")
        all_dates = re.findall(r'\d{2}月\d{2}日', page_text)
        target_dates = [date for date in all_dates if is_target_date(date)]
        unique_target_dates = sorted(list(set(target_dates)))
        
        print(f"   找到 {len(target_dates)} 个目标日期实例，{len(unique_target_dates)} 个唯一目标日期")
        print(f"   目标日期: {unique_target_dates}")
        
        # 3. 尝试通过页面结构关联卡面和日期
        print(f"\n3. 通过页面结构关联卡面和日期:")
        
        # 查找包含日期的活动标题
        lines = page_text.split('\n')
        activity_sections = []
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            
            # 查找包含目标日期的活动行
            dates_in_line = re.findall(r'\d{2}月\d{2}日', line)
            target_dates_in_line = [date for date in dates_in_line if is_target_date(date)]
            
            if target_dates_in_line:
                # 查找这个活动的相关信息
                activity_info = {
                    'line_num': i,
                    'line_text': line,
                    'dates': target_dates_in_line,
                    'cards_nearby': []
                }
                
                # 在前后100行中查找卡面
                search_range = 100
                start_line = max(0, i - search_range)
                end_line = min(len(lines), i + search_range + 1)
                
                for j in range(start_line, end_line):
                    cards_in_line = re.findall(r'☆[345]［[^］]+］[^☆\n]*', lines[j])
                    for card in cards_in_line:
                        card = card.strip()
                        card_match = re.search(r'☆([345])［([^］]+)］(.+)', card)
                        if card_match:
                            activity_info['cards_nearby'].append({
                                'star_level': card_match.group(1),
                                'card_name': card_match.group(2),
                                'character': card_match.group(3).strip(),
                                'full_text': card,
                                'distance': abs(j - i)
                            })
                
                # 按距离排序
                activity_info['cards_nearby'].sort(key=lambda x: x['distance'])
                
                activity_sections.append(activity_info)
        
        print(f"   找到 {len(activity_sections)} 个包含目标日期的活动")
        
        # 显示活动和相关卡面
        for i, activity in enumerate(activity_sections[:5]):  # 只显示前5个
            print(f"\n   活动 {i+1}: {activity['dates']}")
            print(f"     行 {activity['line_num']}: {activity['line_text'][:100]}...")
            print(f"     附近找到 {len(activity['cards_nearby'])} 个卡面:")
            
            for j, card in enumerate(activity['cards_nearby'][:3]):  # 只显示最近的3个
                print(f"       {j+1}. ☆{card['star_level']}［{card['card_name']}］{card['character']} (距离{card['distance']}行)")
        
        # 4. 生成最终的卡面-日期关联
        print(f"\n4. 生成卡面-日期关联:")
        
        final_cards = []
        
        # 方法1: 基于活动关联
        for activity in activity_sections:
            for date in activity['dates']:
                for card in activity['cards_nearby'][:5]:  # 取最近的5个卡面
                    final_cards.append({
                        'date': date,
                        'star_level': card['star_level'],
                        'card_name': card['card_name'],
                        'character': card['character'],
                        'full_text': card['full_text'],
                        'source': 'activity_association',
                        'confidence': 1.0 / (card['distance'] + 1)  # 距离越近置信度越高
                    })
        
        # 方法2: 如果没有找到关联，则使用所有卡面配对所有目标日期
        if not final_cards:
            print("   未找到活动关联，使用全量配对方法")
            for date in unique_target_dates:
                for card in parsed_cards:
                    final_cards.append({
                        'date': date,
                        'star_level': card['star_level'],
                        'card_name': card['card_name'],
                        'character': card['character'],
                        'full_text': card['full_text'],
                        'source': 'full_pairing',
                        'confidence': 0.5
                    })
        
        # 去重并按置信度排序
        unique_final_cards = []
        seen = set()
        
        for card in final_cards:
            key = (card['date'], card['full_text'])
            if key not in seen:
                seen.add(key)
                unique_final_cards.append(card)
        
        # 按日期和置信度排序
        unique_final_cards.sort(key=lambda x: (x['date'], -x['confidence']))
        
        print(f"   最终生成 {len(unique_final_cards)} 个卡面-日期关联")
        
        # 按日期分组显示
        date_groups = {}
        for card in unique_final_cards:
            date = card['date']
            if date not in date_groups:
                date_groups[date] = []
            date_groups[date].append(card)
        
        print(f"\n按日期分组的结果:")
        for date in sorted(date_groups.keys()):
            cards = date_groups[date]
            print(f"\n{date} ({len(cards)}个卡面):")
            for i, card in enumerate(cards[:5]):  # 只显示前5个
                print(f"  {i+1}. ☆{card['star_level']}［{card['card_name']}］{card['character']} (置信度: {card['confidence']:.2f})")
        
        return unique_final_cards
        
    except Exception as e:
        print(f"错误: {e}")
        return []

if __name__ == "__main__":
    print("=" * 80)
    print("从页面提取卡面信息并关联到目标日期")
    print("目标日期: 10日、14日、15日、25日、月末前一天、月末")
    print("=" * 80)
    
    final_cards = extract_cards_and_dates()
    
    if final_cards:
        print(f"\n" + "=" * 80)
        print(f"提取完成！共找到 {len(final_cards)} 个卡面-日期关联")
        print("=" * 80)
    else:
        print("\n未找到任何卡面-日期关联")