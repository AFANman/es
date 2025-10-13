#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
from bs4 import BeautifulSoup
import re

def search_specific_cards():
    """Search for specific cards mentioned by user"""
    
    # Target cards mentioned by user
    target_cards = [
        "［高みに挑み進む星］漣 ジュン",
        "［心揺さぶる導きの星］逆先 夏目"
    ]
    
    # URL to search
    url = "https://gamerch.com/ensemble-star-music/895943"
    
    print(f"搜索页面: {url}")
    print(f"目标卡面:")
    for card in target_cards:
        print(f"  - {card}")
    print()
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, "lxml")
        
        # Search for the target cards
        found_cards = []
        
        # Find all links with card names
        for a in soup.find_all('a', href=True):
            text = a.get_text(strip=True)
            href = a['href']
            
            # Check if this link contains any of our target cards
            for target_card in target_cards:
                if target_card in text:
                    found_cards.append({
                        'card_name': text,
                        'url': href,
                        'target': target_card
                    })
                    print(f"✓ 找到目标卡面: {text}")
                    print(f"  链接: {href}")
                    print()
        
        # Also search for partial matches
        print("=== 搜索部分匹配 ===")
        keywords = ["漣 ジュン", "逆先 夏目", "高みに挑み進む星", "心揺さぶる導きの星"]
        
        for keyword in keywords:
            print(f"\n搜索关键词: {keyword}")
            matches = soup.find_all(text=re.compile(keyword))
            
            if matches:
                for match in matches[:5]:  # Show first 5 matches
                    parent = match.parent if hasattr(match, 'parent') else None
                    if parent and parent.name == 'a':
                        print(f"  找到: {parent.get_text(strip=True)}")
                        print(f"  链接: {parent.get('href', 'N/A')}")
            else:
                print(f"  未找到包含 '{keyword}' 的内容")
        
        # Search for DI:Verse event section
        print("\n=== 搜索 DI:Verse 活动区域 ===")
        diverse_elements = soup.find_all(text=re.compile("DI:Verse"))
        
        for elem in diverse_elements:
            parent = elem.parent if hasattr(elem, 'parent') else None
            if parent:
                # Get the surrounding context
                context = parent.get_text(strip=True)
                print(f"DI:Verse 上下文: {context[:100]}...")
                
                # Look for nearby card links
                nearby_links = parent.find_all('a', href=True)
                if not nearby_links and parent.parent:
                    nearby_links = parent.parent.find_all('a', href=True)
                
                print(f"  附近的链接数量: {len(nearby_links)}")
                for link in nearby_links[:3]:  # Show first 3 links
                    link_text = link.get_text(strip=True)
                    if '［' in link_text and '］' in link_text:
                        print(f"    - {link_text}")
                print()
        
        if not found_cards:
            print("❌ 未找到任何目标卡面")
        else:
            print(f"✓ 总共找到 {len(found_cards)} 个目标卡面")
            
    except Exception as e:
        print(f"错误: {e}")

if __name__ == "__main__":
    search_specific_cards()