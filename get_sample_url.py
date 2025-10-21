#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
from bs4 import BeautifulSoup
import urllib3

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def get_sample_card_url():
    """从列表页获取一个真实的卡面URL"""
    
    # 使用一个已知的列表页URL
    list_url = "https://gamerch.com/ensemble-star-music/entry/895943"
    
    try:
        print(f"正在获取列表页: {list_url}")
        response = requests.get(list_url, timeout=10, verify=False)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 查找卡面链接
        card_links = soup.find_all('a', href=True)
        
        print(f"找到 {len(card_links)} 个链接")
        
        # 查找包含卡面信息的链接
        for link in card_links[:10]:  # 只检查前10个
            href = link.get('href', '')
            text = link.get_text(strip=True)
            
            if 'entry' in href and len(text) > 5:
                if href.startswith('http'):
                    card_url = href
                else:
                    card_url = 'https://gamerch.com' + href.lstrip('/')
                
                print(f"找到卡面链接: {card_url}")
                print(f"链接文本: {text}")
                return card_url
                
        print("未找到合适的卡面链接")
        return None
        
    except Exception as e:
        print(f"错误: {e}")
        return None

if __name__ == "__main__":
    url = get_sample_card_url()
    if url:
        print(f"\n✅ 获取到测试URL: {url}")
    else:
        print("\n❌ 未能获取测试URL")