import os
from datetime import datetime
import re
import sys
from typing import Dict, List, Tuple

try:
    from crawl4ai import WebCrawler, BrowserConfig, CrawlConfig
    HAS_CRAWL4AI = True
except Exception:
    HAS_CRAWL4AI = False

import requests
from bs4 import BeautifulSoup
import pandas as pd
from multithreaded_card_fetcher import MultiThreadedCardFetcher


def crawl_page(url: str) -> Tuple[str, str]:
    """Return (html, markdown) using Crawl4AI if available, else requests.
    """
    if HAS_CRAWL4AI:
        try:
            browser_cfg = BrowserConfig(headless=True)
            crawler = WebCrawler(browser_config=browser_cfg)
            # Minimal config; allow JS for dynamic pages
            crawl_cfg = CrawlConfig()
            result = crawler.crawl(url=url, config=crawl_cfg)
            html = result.html or ""
            md = getattr(result, "markdown", "") or ""
            if html.strip():
                return html, md
        except Exception:
            pass

    # Fallback
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "ja,en-US;q=0.7,en;q=0.3",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }
    import time
    time.sleep(1)  # Add delay to avoid rate limiting
    resp = requests.get(url, headers=headers, timeout=20)
    resp.raise_for_status()
    return resp.text, ""


def find_card_links_loose(soup: BeautifulSoup, base_url: str) -> List[str]:
    """Looser finder for detail links on listing pages.
    - Collect anchors whose href contains '/ensemble-star-music/<digits>'
    - Prefer within the "スカウト追加カード" section but fallback to whole page
    - Do NOT require bracketed text on anchor; normalize to absolute URLs
    """
    urls: List[str] = []
    base_id = re.search(r"ensemble-star-music/(\d+)", base_url)
    base_id_str = base_id.group(1) if base_id else None

    section = soup.find(lambda t: t.name in {"h2", "h3", "div", "section"} and "スカウト追加カード" in t.get_text("\n", strip=True))
    anchors: List[Tuple[str, str]] = []
    if section:
        cur = section
        for _ in range(40):
            cur = cur.find_next_sibling()
            if not cur:
                break
            txt = cur.get_text("\n", strip=True)
            if any(k in txt for k in ["★ リンク一覧", "キャラクター", "IRマス詳細", "必要素材数"]):
                break
            for a in cur.find_all('a', href=True):
                anchors.append((a['href'], a.get_text(strip=True)))
    else:
        for a in soup.find_all('a', href=True):
            anchors.append((a['href'], a.get_text(strip=True)))

    for href, _ in anchors:
        if 'ensemble-star-music/' not in href:
            continue
        m = re.search(r"ensemble-star-music/(\d+)", href)
        if not m:
            continue
        card_id = m.group(1)
        if not card_id or card_id == base_id_str:
            continue
        if href.startswith('http'):
            urls.append(href)
        else:
            urls.append('https://gamerch.com/' + href.lstrip('/'))
    # Deduplicate (no limit on number of cards)
    seen = set()
    dedup: List[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            dedup.append(u)
    return dedup


def find_card_links(soup: BeautifulSoup, base_url: str) -> List[str]:
    """Find detail page links for cards from a listing/campaign page.
    Heuristics:
    - anchors whose href contains '/ensemble-star-music/<digits>'
    - anchor text contains a full-width bracketed card name like ［...］
    - exclude the base url itself
    Limit to a reasonable number to avoid long runs.
    """
    urls: List[str] = []
    base_id = re.search(r"ensemble-star-music/(\d+)", base_url)
    base_id_str = base_id.group(1) if base_id else None

    # Look for the "追加カード" section which contains the card links
    section = soup.find(lambda t: t.name in {"h2", "h3", "div", "section"} and "追加カード" in t.get_text("\n", strip=True))
    anchors: List[Tuple[str, str]] = []
    
    if section:
        # Find the next elements after the "追加カード" heading
        cur = section
        for _ in range(20):
            cur = cur.find_next_sibling()
            if not cur:
                break
            txt = cur.get_text("\n", strip=True)
            # Stop at next major section
            if any(k in txt for k in ["ボーナス効果", "スカウトの確率について", "SCRカラーについて"]):
                break
            for a in cur.find_all('a', href=True):
                anchors.append((a['href'], a.get_text(strip=True)))
    
    # Also check for direct links in the card display area
    card_display_area = soup.find('div', class_=lambda x: x and 'card' in x.lower()) or soup
    for a in card_display_area.find_all('a', href=True):
        text = a.get_text(strip=True)
        # Look for character names in the link text
        if any(name in text for name in ['HiMERU', '天城', '葵']):
            anchors.append((a['href'], text))

    for href, text in anchors:
        if 'ensemble-star-music/' not in href:
            continue
        m = re.search(r"ensemble-star-music/(\d+)", href)
        if not m:
            continue
        card_id = m.group(1)
        if not card_id or card_id == base_id_str:
            continue
        
        # Accept links that either have bracketed names or contain target character names
        has_bracket = re.search(r"\uFF3B[^\uFF3D]+\uFF3D", text)
        has_target_char = any(name in text for name in ['HiMERU', '天城', '葵'])
        
        if not (has_bracket or has_target_char):
            continue
            
        # Normalize absolute URL
        if href.startswith('http'):
            urls.append(href)
        else:
            urls.append('https://gamerch.com/' + href.lstrip('/'))
    
    # Deduplicate preserving order and cap to 10 for targeted extraction
    seen = set()
    dedup: List[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            dedup.append(u)
            if len(dedup) >= 10:
                break
    return dedup


def parse_card_name(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    # Prefer og:title
    og = soup.find("meta", attrs={"property": "og:title"})
    if og and og.get("content"):
        title = og["content"].strip()
        # Try to extract bracketed card name
        m = re.search(r"\uFF3B([^\uFF3D]+)\uFF3D\s*([^\-|]+)", title)  # ［...］ Name
        if m:
            return f"［{m.group(1).strip()}］{m.group(2).strip()}"
        return title
    # Fallback to h1
    h1 = soup.find("h1")
    if h1:
        return h1.get_text(strip=True)
    # Last resort: page title
    if soup.title and soup.title.string:
        t = soup.title.string.strip()
        m = re.search(r"\uFF3B([^\uFF3D]+)\uFF3D\s*([^\-|]+)", t)
        if m:
            return f"［{m.group(1).strip()}］{m.group(2).strip()}"
        return t
    return ""


def extract_cards_from_directory(html: str, base_url: str) -> List[Tuple[str, str]]:
    """Extract card detail links and event names from yearly event directory page for target dates.
    Target dates: 10th, 14th, 15th, 25th, month-end (30th/31st), day before month-end (29th/30th)
    Returns: List of (card_url, event_name) tuples
    """
    soup = BeautifulSoup(html, "lxml")
    
    def is_target_date(day: int, month: int) -> bool:
        """Check if the given day is a target date"""
        if day in [10, 14, 15, 25]:
            return True
        # Check for month-end and day before month-end
        if month in [1, 3, 5, 7, 8, 10, 12]:  # 31-day months
            return day in [30, 31]
        elif month in [4, 6, 9, 11]:  # 30-day months
            return day in [29, 30]
        elif month == 2:  # February (assume non-leap year)
            return day in [27, 28]
        return False
    
    def find_cards_by_date_with_dynamic_event_names(date_pattern: str) -> List[Tuple[str, str]]:
        """Find card links by date and dynamically extract the actual event names"""
        cards = []
        
        # Strategy 1: Look for h2/h3 headers that contain the date pattern
        headers = soup.find_all(['h2', 'h3'], string=re.compile(date_pattern))
        
        print(f"  查找日期模式 '{date_pattern}': 在标题中找到 {len(headers)} 个匹配")
        
        for header in headers:
            header_text = header.get_text(strip=True)
            print(f"    标题: {header_text}")
            
            # Extract event name from header
            actual_event_name = extract_event_name_from_context(header_text, date_pattern)
            
            # Find the next sibling elements until we hit another header
            current = header.next_sibling
            section_cards = []
            
            while current:
                # Stop if we hit another header of the same or higher level
                if (hasattr(current, 'name') and 
                    current.name in ['h1', 'h2', 'h3'] and 
                    current != header):
                    break
                
                # Look for card links in this element
                if hasattr(current, 'find_all'):
                    card_links = current.find_all('a', href=True)
                    
                    for link in card_links:
                        href = link.get('href', '')
                        text = link.get_text(strip=True)
                        
                        # Check if this is a card link
                        if ('ensemble-star-music/' in href and 
                            re.search(r'/\d+$', href) and 
                            text.startswith('［') and '］' in text and
                            len(text) > 10 and  # Card names are usually longer
                            not text.endswith('一覧') and  # Exclude list pages
                            'カード一覧' not in text):  # Exclude card list pages
                            
                            # Normalize URL
                            if href.startswith('http'):
                                card_url = href
                            else:
                                card_url = 'https://gamerch.com' + href.lstrip('/')
                            
                            section_cards.append((card_url, actual_event_name, text))
                
                current = current.next_sibling
            
            # Add all found cards with their actual event names
            for card_url, event_name, card_text in section_cards:
                cards.append((card_url, event_name))
            
            if section_cards:
                print(f"    在标题 '{actual_event_name}' 区域找到 {len(section_cards)} 个卡面")
        
        # Strategy 2: If no headers found, look for date in table cells or divs
        if not cards:
            print(f"  未在标题中找到，尝试在表格和div中查找...")
            
            # Find all elements containing the date
            date_elements = soup.find_all(string=re.compile(date_pattern))
            
            for date_elem in date_elements:
                parent = date_elem.parent if hasattr(date_elem, 'parent') else None
                if not parent:
                    continue
                
                # Look for the closest table row or div container
                container = parent
                for i in range(5):  # Go up max 5 levels
                    if container and container.name in ['tr', 'div', 'td', 'th']:
                        break
                    if container and container.parent:
                        container = container.parent
                    else:
                        break
                
                if container:
                    # Extract the actual event name from the container
                    container_text = container.get_text(strip=True)
                    actual_event_name = extract_event_name_from_context(container_text, date_pattern)
                    
                    # Look for card links in this specific container only
                    card_links = container.find_all('a', href=True)
                    
                    section_cards = []
                    for link in card_links:
                        href = link.get('href', '')
                        text = link.get_text(strip=True)
                        
                        # Check if this is a card link
                        if ('ensemble-star-music/' in href and 
                            re.search(r'/\d+$', href) and 
                            text.startswith('［') and '］' in text and
                            len(text) > 10 and  # Card names are usually longer
                            not text.endswith('一覧') and  # Exclude list pages
                            'カード一覧' not in text):  # Exclude card list pages
                            
                            # Normalize URL
                            if href.startswith('http'):
                                card_url = href
                            else:
                                card_url = 'https://gamerch.com' + href.lstrip('/')
                            
                            section_cards.append((card_url, actual_event_name, text))
                    
                    # Add all found cards with their actual event names
                    for card_url, event_name, card_text in section_cards:
                        cards.append((card_url, event_name))
                    
                    if section_cards:
                        print(f"    在容器 '{actual_event_name}' 中找到 {len(section_cards)} 个卡面")
        
        return cards
    
    def extract_event_name_from_context(context_text: str, date_pattern: str) -> str:
        """Extract the actual event name from the context text"""
        
        # Remove the regex special characters for simple matching
        simple_date = date_pattern.replace('.*', '').replace('\\', '')
        
        print(f"    提取活动名 - 日期: {simple_date}")
        print(f"    上下文片段: {context_text[:200]}...")
        
        # First, try to find h2/h3 headers that contain the date
        lines = context_text.split('\n')
        for line in lines:
            line = line.strip()
            if simple_date in line and len(line) < 200:  # Reasonable header length
                # Clean up the line to get the event name
                event_name = line.replace(simple_date, '').strip()
                # Remove common prefixes/suffixes
                event_name = re.sub(r'^[　\s]*', '', event_name)  # Remove leading spaces
                event_name = re.sub(r'[　\s]*$', '', event_name)  # Remove trailing spaces
                
                if event_name and 5 <= len(event_name) <= 100:
                    print(f"    找到活动名: {event_name}")
                    return f"{simple_date}　{event_name}"
        
        # Try to find the event name pattern: "日期　活动名"
        # Look for the date followed by event information
        patterns = [
            # Pattern 1: 日期　活动名 (with full-width space, more precise)
            rf'{re.escape(simple_date)}[　\s]+([^0-9\n]+?)(?=\d{{1,2}}月\d{{1,2}}日|$)',
            # Pattern 2: 日期 活动名 (with regular space, more precise)
            rf'{re.escape(simple_date)}[　\s]+([^\n]+?)(?=\d{{1,2}}月\d{{1,2}}日|$)',
        ]
        
        for i, pattern in enumerate(patterns):
            match = re.search(pattern, context_text)
            if match:
                event_text = match.group(1).strip()
                # Clean up the event text
                event_text = re.sub(r'\s+', ' ', event_text)  # Normalize spaces
                event_text = event_text.replace('\n', ' ').replace('\t', ' ')
                
                # Remove common noise
                event_text = re.sub(r'^[　\s]*', '', event_text)
                event_text = re.sub(r'[　\s]*$', '', event_text)
                
                # If the event text is reasonable length, use it
                if 5 <= len(event_text) <= 100:
                    print(f"    模式{i+1}找到活动名: {event_text}")
                    return f"{simple_date}　{event_text}"
        
        # Fallback: try to identify specific event types
        if 'DI:Verse' in context_text:
            print(f"    回退到DI:Verse活动")
            return f"{simple_date}　スカウト！DI:Verse"
        elif 'フィーチャースカウト' in context_text:
            if 'ライカ編' in context_text:
                print(f"    回退到フィーチャースカウト ライカ編")
                return f"{simple_date}　フィーチャースカウト ライカ編"
            else:
                print(f"    回退到フィーチャースカウト")
                return f"{simple_date}　フィーチャースカウト"
        elif 'スカウト' in context_text:
            print(f"    回退到通用スカウト")
            return f"{simple_date}　スカウト"
        elif 'イベント' in context_text:
            print(f"    回退到通用イベント")
            return f"{simple_date}　イベント"
        else:
            print(f"    未找到活动名，使用默认")
            return f"{simple_date}　未知活动"
    
    # Extract card links and their associated event names
    card_event_pairs = []
    
    # Define target dates to search for with dynamic event name extraction
    # Updated to include comprehensive full-year coverage (2024-2025)
    target_dates = [
        # December 2024 (latest potential dates)
        "12月31日", "12月30日", "12月29日", "12月28日", "12月27日", "12月26日", "12月25日",
        "12月24日", "12月23日", "12月22日", "12月21日", "12月20日", "12月19日", "12月18日",
        "12月17日", "12月16日", "12月15日", "12月14日", "12月13日", "12月12日", "12月11日",
        "12月10日", "12月9日", "12月8日", "12月7日", "12月6日", "12月5日", "12月4日",
        "12月3日", "12月2日", "12月1日",
        
        # November 2024
        "11月30日", "11月29日", "11月28日", "11月27日", "11月26日", "11月25日", "11月24日",
        "11月23日", "11月22日", "11月21日", "11月20日", "11月19日", "11月18日", "11月17日",
        "11月16日", "11月15日", "11月14日", "11月13日", "11月12日", "11月11日", "11月10日",
        "11月9日", "11月8日", "11月7日", "11月6日", "11月5日", "11月4日", "11月3日", "11月2日", "11月1日",
        
        # October 2024
        "10月31日", "10月30日", "10月29日", "10月28日", "10月27日", "10月26日", "10月25日",
        "10月24日", "10月23日", "10月22日", "10月21日", "10月20日", "10月19日", "10月18日",
        "10月17日", "10月16日", "10月15日", "10月14日", "10月13日", "10月12日", "10月11日",
        "10月10日", "10月9日", "10月8日", "10月7日", "10月6日", "10月5日", "10月4日",
        "10月3日", "10月2日", "10月1日",
        
        # September 2024
        "09月30日", "09月29日", "09月28日", "09月27日", "09月26日", "09月25日", "09月24日",
        "09月23日", "09月22日", "09月21日", "09月20日", "09月19日", "09月18日", "09月17日",
        "09月16日", "09月15日", "09月14日", "09月13日", "09月12日", "09月11日", "09月10日",
        "09月9日", "09月8日", "09月7日", "09月6日", "09月5日", "09月4日", "09月3日", "09月2日", "09月1日",
        "9月30日", "9月25日", "9月15日", "9月10日", "9月5日", "9月1日",
        
        # August 2024
        "08月31日", "08月30日", "08月29日", "08月28日", "08月27日", "08月26日", "08月25日",
        "08月24日", "08月23日", "08月22日", "08月21日", "08月20日", "08月19日", "08月18日",
        "08月17日", "08月16日", "08月15日", "08月14日", "08月13日", "08月12日", "08月11日",
        "08月10日", "08月9日", "08月8日", "08月7日", "08月6日", "08月5日", "08月4日",
        "08月3日", "08月2日", "08月1日",
        "8月31日", "8月25日", "8月15日", "8月10日", "8月5日", "8月1日",
        
        # July 2024
        "07月31日", "07月30日", "07月29日", "07月28日", "07月27日", "07月26日", "07月25日",
        "07月24日", "07月23日", "07月22日", "07月21日", "07月20日", "07月19日", "07月18日",
        "07月17日", "07月16日", "07月15日", "07月14日", "07月13日", "07月12日", "07月11日",
        "07月10日", "07月9日", "07月8日", "07月7日", "07月6日", "07月5日", "07月4日",
        "07月3日", "07月2日", "07月1日",
        "7月31日", "7月25日", "7月15日", "7月10日", "7月5日", "7月1日",
        
        # June 2024
        "06月30日", "06月29日", "06月28日", "06月27日", "06月26日", "06月25日", "06月24日",
        "06月23日", "06月22日", "06月21日", "06月20日", "06月19日", "06月18日", "06月17日",
        "06月16日", "06月15日", "06月14日", "06月13日", "06月12日", "06月11日", "06月10日",
        "06月9日", "06月8日", "06月7日", "06月6日", "06月5日", "06月4日", "06月3日",
        "06月2日", "06月1日",
        "6月30日", "6月25日", "6月15日", "6月10日", "6月5日", "6月1日",
        
        # May 2024
        "05月31日", "05月30日", "05月29日", "05月28日", "05月27日", "05月26日", "05月25日",
        "05月24日", "05月23日", "05月22日", "05月21日", "05月20日", "05月19日", "05月18日",
        "05月17日", "05月16日", "05月15日", "05月14日", "05月13日", "05月12日", "05月11日",
        "05月10日", "05月9日", "05月8日", "05月7日", "05月6日", "05月5日", "05月4日",
        "05月3日", "05月2日", "05月1日",
        "5月31日", "5月25日", "5月15日", "5月10日", "5月5日", "5月1日",
        
        # April 2024
        "04月30日", "04月29日", "04月28日", "04月27日", "04月26日", "04月25日", "04月24日",
        "04月23日", "04月22日", "04月21日", "04月20日", "04月19日", "04月18日", "04月17日",
        "04月16日", "04月15日", "04月14日", "04月13日", "04月12日", "04月11日", "04月10日",
        "04月9日", "04月8日", "04月7日", "04月6日", "04月5日", "04月4日", "04月3日",
        "04月2日", "04月1日",
        "4月30日", "4月25日", "4月15日", "4月10日", "4月5日", "4月1日",
        
        # March 2024
        "03月31日", "03月30日", "03月29日", "03月28日", "03月27日", "03月26日", "03月25日",
        "03月24日", "03月23日", "03月22日", "03月21日", "03月20日", "03月19日", "03月18日",
        "03月17日", "03月16日", "03月15日", "03月14日", "03月13日", "03月12日", "03月11日",
        "03月10日", "03月9日", "03月8日", "03月7日", "03月6日", "03月5日", "03月4日",
        "03月3日", "03月2日", "03月1日",
        "3月31日", "3月25日", "3月15日", "3月10日", "3月5日", "3月1日",
        
        # February 2024
        "02月29日", "02月28日", "02月27日", "02月26日", "02月25日", "02月24日", "02月23日",
        "02月22日", "02月21日", "02月20日", "02月19日", "02月18日", "02月17日", "02月16日",
        "02月15日", "02月14日", "02月13日", "02月12日", "02月11日", "02月10日", "02月9日",
        "02月8日", "02月7日", "02月6日", "02月5日", "02月4日", "02月3日", "02月2日", "02月1日",
        "2月29日", "2月28日", "2月25日", "2月20日", "2月15日", "2月10日", "2月5日", "2月1日",
        
        # January 2024
        "01月31日", "01月30日", "01月29日", "01月28日", "01月27日", "01月26日", "01月25日",
        "01月24日", "01月23日", "01月22日", "01月21日", "01月20日", "01月19日", "01月18日",
        "01月17日", "01月16日", "01月15日", "01月14日", "01月13日", "01月12日", "01月11日",
        "01月10日", "01月9日", "01月8日", "01月7日", "01月6日", "01月5日", "01月4日",
        "01月3日", "01月2日", "01月1日",
        "1月31日", "1月25日", "1月20日", "1月15日", "1月10日", "1月5日", "1月1日",
    ]
    
    print("=== 按日期动态提取卡面和活动名 ===")
    
    # Extract cards for each target date with dynamic event names
    for date_pattern in target_dates:
        print(f"\n处理日期: {date_pattern}")
        section_cards = find_cards_by_date_with_dynamic_event_names(date_pattern)
        if section_cards:
            print(f"在 '{date_pattern}' 区域找到 {len(section_cards)} 个卡面")
            card_event_pairs.extend(section_cards)
        else:
            print(f"在 '{date_pattern}' 区域未找到卡面")
    
    # If no cards found in specific event sections, fall back to general extraction
    if not card_event_pairs:
        print("未在特定活动区域找到卡面，使用通用提取方法...")
        
        # Find all card links without date filtering
        for a in soup.find_all('a', href=True):
            href = a['href']
            text = a.get_text(strip=True)
            
            # Look for card links with bracketed names
            if ('ensemble-star-music/' in href and 
                re.search(r'/\d+$', href) and 
                text.startswith('［') and '］' in text and
                len(text) > 10 and  # Card names are usually longer
                not text.endswith('一覧') and  # Exclude list pages
                'カード一覧' not in text):  # Exclude card list pages
                
                # Normalize URL
                if href.startswith('http'):
                    card_url = href
                else:
                    card_url = 'https://gamerch.com' + href.lstrip('/')
                
                # Use a generic event name
                event_name = "【通用提取】"
                
                card_event_pairs.append((card_url, event_name))
    
    # Remove duplicates while preserving order
    seen = set()
    unique_pairs = []
    for card_url, event_name in card_event_pairs:
        if card_url not in seen:
            seen.add(card_url)
            unique_pairs.append((card_url, event_name))
    
    print(f"\n总共找到 {len(unique_pairs)} 个卡面详情链接")
    
    # Show event distribution
    event_counts = {}
    for _, event_name in unique_pairs:
        event_counts[event_name] = event_counts.get(event_name, 0) + 1
    
    print("活动分布:")
    for event, count in event_counts.items():
        print(f"  {event}: {count} 个卡面")
    
    # Return all found cards (no limit)
    return unique_pairs


def extract_event_name_from_listing(soup: BeautifulSoup) -> str:
    """Extract the event/scout name from listing page.
    Priority:
    1) Text containing 'クロススカウト・' and '／inspired' or '／empathy'
    2) Any text containing 'アンビバレンス' with 'クロススカウト'
    3) Page title stripped of site prefix like '【あんスタMusic】'
    """
    full_text = soup.get_text("\n", strip=True)
    # 1) Explicit inspired/empathy
    m = re.search(r"(クロススカウト・[^\n／]+／(?:inspired|empathy))", full_text)
    if m:
        return m.group(1).strip()
    # 2) クロススカウト＋アンビバレンス
    m = re.search(r"(クロススカウト・[^\n]*アンビバレンス[^\n]*)", full_text)
    if m:
        return m.group(1).strip()
    # 3) Title fallback
    if soup.title and soup.title.string:
        t = soup.title.string.strip()
        # Remove leading site mark
        t = re.sub(r"^【あんスタMusic】", "", t)
        t = re.sub(r"\s*-\s*あんスタMusic攻略wiki\s*\|\s*Gamerch\s*$", "", t)
        return t.strip()
    return ""


def extract_additional_cards_from_listing(soup: BeautifulSoup) -> List[Dict[str, str]]:
    """Extract additional cards under the listing page without visiting detail pages.
    Strategy: parse the "スカウトの確率について" block that enumerates ☆5/☆4/☆3 cards
    and map bracketed names to rarities.
    Returns a list of rows with at least 卡面名称, レアリティ, イベント名.
    """
    text = soup.get_text("\n", strip=True)
    rows: List[Dict[str, str]] = []
    event_name = extract_event_name_from_listing(soup)
    
    # Look for the probability section that lists the specific cards
    prob_section = re.search(r"スカウトの確率について.*?☆5カード.*?☆4カード.*?☆3カード", text, re.DOTALL)
    if prob_section:
        prob_text = prob_section.group(0)
        
        # Extract card names with their rarities from probability section
        card_patterns = [
            (r"☆5カード.*?（.*?で(［[^］]+］[^）]+)）", "☆5"),
            (r"☆4カード.*?（.*?で(［[^］]+］[^）]+)）", "☆4"), 
            (r"☆3カード.*?（.*?で(［[^］]+］[^）]+)）", "☆3")
        ]
        
        for pattern, rarity in card_patterns:
            match = re.search(pattern, prob_text)
            if match:
                card_name = match.group(1).strip()
                rows.append({
                    "卡面名称": card_name,
                    "レアリティ": rarity,
                    "イベント名": event_name,
                })
    
    # Fallback: collect bracketed names from DOM text nodes
    if not rows:
        collected: List[str] = []
        for tnode in soup.find_all(string=re.compile(r"［[^］]+］")):
            s = (tnode.strip() if isinstance(tnode, str) else str(tnode)).strip()
            # Expect format like "［裏表アンビバレンス］HiMERU"
            if not s or "アンビバレンス" not in s:
                continue
            if s.startswith("☆"):
                # Skip lines annotated with star at beginning (likely unrelated samples)
                continue
            # Normalize whitespace
            s = re.sub(r"\s+", " ", s)
            if s not in collected:
                collected.append(s)
            if len(collected) >= 3:
                break

        # Assign rarities by appearance order: ☆5, ☆4, ☆3
        rarity_order = ["☆5", "☆4", "☆3"]
        for idx, name in enumerate(collected[:3]):
            rarity = rarity_order[idx] if idx < len(rarity_order) else ""
            rows.append({
                "卡面名称": name,
                "レアリティ": rarity,
                "イベント名": event_name,
            })
    
    return rows


def extract_basic_info(soup: BeautifulSoup) -> Dict[str, str]:
    info = {
        "レアリティ": "",
        "タイプ/属性": "",
        "ファン上限": "",
        "追加日": "",
    }
    # Find a block that contains 基本情報
    block = soup.find(lambda t: t.name in {"h2", "h3", "div", "section"} and "基本情報" in t.get_text("\n", strip=True))
    text = ""
    if block:
        # Gather some siblings to include actual content
        texts = [block.get_text("\n", strip=True)]
        sib = block.find_next_sibling()
        for _ in range(5):
            if not sib:
                break
            texts.append(sib.get_text("\n", strip=True))
            sib = sib.find_next_sibling()
        text = "\n".join(texts)
    else:
        # Broader text search
        text = soup.get_text("\n", strip=True)

    # Try table-like label-value extraction
    def find_label(label: str) -> str:
        tag = soup.find(string=re.compile(label))
        if tag:
            parent = getattr(tag, 'parent', None)
            if parent:
                # Same-line value
                full = parent.get_text("\n", strip=True)
                m = re.search(label + r"\s*([^\n]+)", full)
                if m:
                    return m.group(1).strip()
                # Next sibling value
                for sib in parent.find_next_siblings():
                    val = sib.get_text("\n", strip=True)
                    if val:
                        return val
        return ""

    info["レアリティ"] = info["レアリティ"] or find_label("レアリティ")
    info["タイプ/属性"] = info["タイプ/属性"] or find_label("タイプ/属性")
    info["ファン上限"] = info["ファン上限"] or find_label("ファン上限")
    info["追加日"] = info["追加日"] or find_label("追加日")

    # Simple regex extractions
    m = re.search(r"レアリティ\s*([☆★]?\d+)", text)
    if m:
        info["レアリティ"] = m.group(1)
    m = re.search(r"タイプ/属性\s*([^\n]+)", text)
    if m:
        info["タイプ/属性"] = m.group(1).strip()
    m = re.search(r"(無凸)?ファン上限\s*([0-9,]+)\s*人?", text)
    if m:
        info["ファン上限"] = m.group(2).replace(",", "")
    # 追加日取整行（优先首个匹配的整行）
    m = re.search(r"^追加日\s*([^\n]+)$", text, re.M)
    if m:
        info["追加日"] = m.group(1).strip()
    return info


def extract_status(soup: BeautifulSoup) -> Dict[str, Dict[str, str]]:
    # status[列][行] = 値  e.g., status['初期値']['総合値'] = '23510'
    status: Dict[str, Dict[str, str]] = {}
    target_table = None
    for table in soup.find_all("table"):
        t = table.get_text("\n", strip=True)
        if all(k in t for k in ["総合値", "Da", "Vo", "Pf"]):
            target_table = table
            break
    if not target_table:
        return status

    # Extract column headers (初期値 / 無凸MAX値 / 完凸MAX値)
    columns: List[str] = []
    for tr in target_table.find_all("tr"):
        cells = [c.get_text(strip=True) for c in tr.find_all(["th", "td"])]
        if any(x in cells for x in ["初期値", "無凸MAX値", "完凸MAX値"]):
            # First cell likely row header placeholder
            if len(cells) >= 2:
                columns = [c for c in cells[1:] if c]
            break
    if not columns:
        columns = ["初期値", "無凸MAX値", "完凸MAX値"]

    def as_num(s: str) -> str:
        s = s.replace(",", "").replace("-", "").strip()
        return s

    for tr in target_table.find_all("tr"):
        cells = [c.get_text(strip=True) for c in tr.find_all(["th", "td"])]
        if not cells:
            continue
        row_label = cells[0]
        if row_label in ["総合値", "Da", "Vo", "Pf"]:
            for idx, col in enumerate(columns):
                if idx + 1 < len(cells):
                    status.setdefault(col, {})[row_label] = as_num(cells[idx + 1])
    return status


def extract_skills(soup: BeautifulSoup) -> Dict[str, Dict[str, str]]:
    skills = {
        "センタースキル": {"名称": "", "効果": ""},
        "ライブスキル": {"名称": "", "効果": ""},
        "サポートスキル": {"名称": "", "効果": ""},
    }

    full_text = soup.get_text("\n", strip=True)
    
    # Narrow to skills section when possible
    section_start = full_text.find("センター/ライブ/サポートスキル")
    skills_text = full_text
    if section_start != -1:
        skills_text = full_text[section_start:]
        # Cut at next major section, but be more conservative to preserve support skill content
        for marker in ["アイドルロード", "必要素材数"]:
            idx = skills_text.find(marker)
            if idx != -1:
                skills_text = skills_text[:idx]
                break
        # Only cut at スカウト画面 if it's far enough from サポートスキル
        scout_idx = skills_text.find("スカウト画面")
        support_idx = skills_text.find("サポートスキル")
        if scout_idx != -1 and support_idx != -1 and scout_idx - support_idx > 200:
            skills_text = skills_text[:scout_idx]

    # Center skill: prefer explicit name format then fallback to line scanning
    center_name = ""
    center_eff = ""

    # Strategy 1: Look for center skill name in quotes format
    center_name_match = re.search(r'センタースキル[^「]*「([^」]+)」', skills_text)
    if center_name_match:
        center_name = center_name_match.group(1)
    else:
        # Strategy 1b: Line-by-line scanning for center skill name
        lines = skills_text.splitlines()
        for i, line in enumerate(lines):
            line = line.strip()
            if "センタースキル" in line:
                # Look for the next non-empty line that could be a skill name
                for j in range(i + 1, min(i + 4, len(lines))):  # Check next 3 lines
                    potential_name = lines[j].strip()
                    if (potential_name and 
                        not re.search(r'効果|項目|％|up|UP|固定', potential_name) and
                        len(potential_name) > 2):
                        center_name = potential_name
                        break

        # Strategy 2: Look for known skill names in the full page text
        if not center_name:
            # Search in the full page text instead of just skills_text
            lines = full_text.splitlines()
            
            for i, line in enumerate(lines):
                line = line.strip()
                # Look for lines that could be skill names
                if (line and 
                    re.match(r'^[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAFー]+$', line) and  # Only Japanese characters (hiragana, katakana, kanji)
                    3 <= len(line) <= 15 and  # Reasonable length
                    not re.search(r'効果|項目|タイプ|％|up|UP|固定|一覧|リンク|詳細|スキル|カード|衣装|背景|楽曲', line)):
                    # Check if this line is near センタースキル context
                    context_start = max(0, i-5)
                    context_end = min(len(lines), i+5)
                    context = ' '.join(lines[context_start:context_end])
                    if 'センタースキル' in context:
                        center_name = line
                        break
    
    # Find effect
    for line in full_text.splitlines():
        if (not center_eff) and ("固定" in line or "タイプ" in line) and ("％" in line or re.search(r"\bup\b|\bUP\b", line)):
            center_eff = line.strip()
            break
    
    # Only derive name from effect as last resort if no real name found
    if not center_name and center_eff:
        m = re.search(r"([A-Za-zァ-ンヴー]+)タイプの(Da|Vo|Pf).*?％up", center_eff)
        if m:
            center_name = f"{m.group(1)}タイプ {m.group(2)}アップ"
    
    skills["センタースキル"]["名称"] = center_name
    skills["センタースキル"]["効果"] = center_eff

    # Live skill
    # Extract skill name - it's usually the line right after "ライブスキル"
    live_start = full_text.find("ライブスキル")
    if live_start != -1:
        live_section = full_text[live_start:live_start+1000]
        lines = live_section.split('\n')
        if len(lines) > 1:
            # The skill name is typically the second line
            potential_name = lines[1].strip()
            if potential_name and not re.search(r"Lv\.|初期|無凸|完凸", potential_name):
                skills["ライブスキル"]["名称"] = potential_name
    
    # Collect level lines within ライブスキル block
    m_live_block = re.search(r"ライブスキル[\s\S]*?(?=サポートスキル|スカウト画面|取得できるスキル|$)", full_text)
    if m_live_block:
        block = m_live_block.group(0)
        live_lines: List[str] = []
        for line in block.splitlines():
            if re.search(r"Lv\.[0-9]+：", line):
                live_lines.append(line.strip())
        if live_lines:
            skills["ライブスキル"]["効果"] = " / ".join(live_lines)
    
    # Support skill - find the correct サポートスキル section that contains skill details
    # Look for サポートスキル followed by skill content (not navigation elements)
    support_pattern = r"サポートスキル\s*\n([^\n]+)\s*\n初期"
    support_match = re.search(support_pattern, full_text)
    if support_match:
        skill_name = support_match.group(1).strip()
        if skill_name and not re.search(r"Lv\.|初期|無凸|完凸|スカウト", skill_name):
            skills["サポートスキル"]["名称"] = skill_name
    
    # Collect level lines within サポートスキル block using full_text
    # Find the support skill section and extract all Lv. lines
    # Use the extracted skill name if available
    support_skill_name = skills["サポートスキル"]["名称"]
    support_start = -1
    
    if support_skill_name:
        # Try to find the specific skill section
        support_start = full_text.find(f"サポートスキル\n{support_skill_name}")
    
    if support_start == -1:
        # Fallback: find any サポートスキル section with skill content
        support_match = re.search(r"サポートスキル\s*\n([^\n]+)\s*\n初期", full_text)
        if support_match:
            skill_name = support_match.group(1).strip()
            support_start = full_text.find(f"サポートスキル\n{skill_name}")
    
    if support_start != -1:
        # Extract content from support skill start to next major section
        support_end = full_text.find("スカウト画面", support_start)
        if support_end == -1:
            support_end = len(full_text)
        
        support_content = full_text[support_start:support_end]
        
        sup_lines: List[str] = []
        for line in support_content.splitlines():
            if re.search(r"Lv\.[0-9]+：", line):
                sup_lines.append(line.strip())
        
        if sup_lines:
            skills["サポートスキル"]["効果"] = " / ".join(sup_lines)

    return skills


def extract_road_items(soup: BeautifulSoup) -> str:
    # Prefer DOM-based extraction: find heading then collect following content until next section
    heading = soup.find(lambda t: t.name in {"h2", "h3", "div", "section"} and "取得できるスキル/アイテム" in t.get_text("\n", strip=True))
    if heading:
        items: List[str] = []
        cur = heading
        # Walk a few siblings to capture lists and paragraphs
        for i in range(8):
            cur = cur.find_next_sibling()
            if not cur:
                break
            txt = cur.get_text("\n", strip=True)
            if not txt:
                continue
            if any(k in txt for k in ["必要素材数", "IRマス詳細", "合計ステータス", "横にスクロール"]):
                break
            # collect meaningful lines
            for ln in txt.splitlines():
                ln = ln.strip()
                if not ln:
                    continue
                if re.search(r"(スキル|ピース|アイテム|MV|ルーム衣装|SPP|背景|ボイス)", ln):
                    print(f"DEBUG extract_road_items: Adding line: '{ln}'")
                    items.append(ln)
        if items:
            result = "；".join(items)
            print(f"DEBUG extract_road_items: DOM-based result: '{result}'")
            return result

    # Fallback: text block between headings - try broader search
    text = soup.get_text("\n", strip=True)
    
    # Try to find the section with MV衣装 etc. directly
    mv_pattern = r"取得できるスキル/アイテム[\s\S]*?(MV衣装[^\n]*|ルーム衣装[^\n]*|背景[^\n]*|SPP[^\n]*)"
    mv_matches = re.findall(mv_pattern, text)
    
    # Also try the original pattern but with more flexible ending
    m = re.search(r"取得できるスキル/アイテム\n([\s\S]+?)(?:必要素材数|IRマス詳細|合計ステータス|横にスクロール|$)", text)
    if m:
        content = m.group(1)
        lines = [ln.strip() for ln in content.splitlines() if ln.strip()]
        picks = []
        for ln in lines:
            if re.search(r"(スキル|ピース|アイテム|MV|ルーム衣装|SPP|背景|ボイス)", ln):
                picks.append(ln)
        if picks:
            return "；".join(picks)

    # Last resort: robust line scanning with better SPP handling
    items: List[str] = []
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        ln = ln.strip()
        if re.match(r"^(ライブスキル「.+」|サポートスキル「.+」|MV衣装.+|ルーム衣装.+|SPP.+)$", ln):
            # Special handling for SPP lines that might be split
            if ln.startswith("SPP「") and not ln.endswith("」"):
                # Look for the closing quote in the next few lines
                full_spp = ln
                for j in range(i + 1, min(i + 3, len(lines))):
                    next_line = lines[j].strip()
                    full_spp += next_line
                    if "」" in next_line:
                        break
                items.append(full_spp)
            else:
                items.append(ln)
    return "；".join(items)


def build_row(card_name: str, basic: Dict[str, str], status: Dict[str, Dict[str, str]], skills: Dict[str, Dict[str, str]], road_items: str) -> Dict[str, str]:
    
    row = {
        "卡面名称": card_name,
        "レアリティ": basic.get("レアリティ", ""),
        "タイプ/属性": basic.get("タイプ/属性", ""),
        "ファン上限": basic.get("ファン上限", ""),
        "追加日": basic.get("追加日", ""),
        "イベント名": "",
        "初期値 総合値": status.get("初期値", {}).get("総合値", ""),
        "初期値 Da": status.get("初期値", {}).get("Da", ""),
        "初期値 Vo": status.get("初期値", {}).get("Vo", ""),
        "初期値 Pf": status.get("初期値", {}).get("Pf", ""),
        "無凸MAX値 総合値": status.get("無凸MAX値", {}).get("総合値", ""),
        "無凸MAX値 Da": status.get("無凸MAX値", {}).get("Da", ""),
        "無凸MAX値 Vo": status.get("無凸MAX値", {}).get("Vo", ""),
        "無凸MAX値 Pf": status.get("無凸MAX値", {}).get("Pf", ""),
        "完凸MAX値 総合値": status.get("完凸MAX値", {}).get("総合値", ""),
        "完凸MAX値 Da": status.get("完凸MAX値", {}).get("Da", ""),
        "完凸MAX値 Vo": status.get("完凸MAX値", {}).get("Vo", ""),
        "完凸MAX値 Pf": status.get("完凸MAX値", {}).get("Pf", ""),
        "センタースキル 名称": skills.get("センタースキル", {}).get("名称", ""),
        "センタースキル 効果": skills.get("センタースキル", {}).get("効果", ""),
        "ライブスキル 名称": skills.get("ライブスキル", {}).get("名称", ""),
        "ライブスキル 効果": skills.get("ライブスキル", {}).get("効果", ""),
        "サポートスキル 名称": skills.get("サポートスキル", {}).get("名称", ""),
        "サポートスキル 効果": skills.get("サポートスキル", {}).get("効果", ""),
        "取得できるスキル/アイテム": road_items,
    }
    return row


def map_to_template(row: Dict[str, str], columns_order: List[str], use_initial_stats: bool = False) -> Dict[str, str]:
    """Map parsed row (Japanese keys) to template columns (Chinese keys).
    
    Args:
        row: The parsed row data
        columns_order: The column order from template
        use_initial_stats: If True, use 無凸MAX値 for stats (一卡); if False, prefer 完凸MAX値 (満破)
    """
    # Determine card rarity
    rarity = row.get("レアリティ", "").strip()
    card_name = row.get("卡面名称", "")
    is_5_star = rarity == "☆5" or "☆5" in card_name or "★5" in card_name
    is_4_star = rarity == "☆4" or "☆4" in card_name or "★4" in card_name
    is_3_star = rarity == "☆3" or "☆3" in card_name or "★3" in card_name
    
    def pick_stat(key: str) -> str:
        # For 3-star and 4-star cards, don't show stats
        if is_3_star or is_4_star:
            return ""
            
        if use_initial_stats:
            # For initial stats (一卡), use 無凸MAX値 instead of 初期値
            return (
                row.get(f"無凸MAX値 {key}")
                or row.get(f"完凸MAX値 {key}")
                or row.get(f"初期値 {key}")
                or ""
            )
        else:
            # For max stats (満破), prefer 完凸MAX値 then 無凸MAX値 then 初期値
            return (
                row.get(f"完凸MAX値 {key}")
                or row.get(f"無凸MAX値 {key}")
                or row.get(f"初期値 {key}")
                or ""
            )

    # Parse live Lv5 from combined effect
    live_eff = row.get("ライブスキル 効果", "") or ""
    m_lv5 = re.search(r"Lv\.5：([^/\n]+)", live_eff)
    live_lv5 = m_lv5.group(1).strip() if m_lv5 else ""

    # Parse support Lv3 from combined effect
    sup_eff = row.get("サポートスキル 効果", "") or ""
    m_lv3 = re.search(r"Lv\.3：([^/\n]+)", sup_eff)
    sup_lv3 = m_lv3.group(1).strip() if m_lv3 else ""

    # Split road items
    mv_items: List[str] = []
    room_items: List[str] = []
    bg_items: List[str] = []
    spp_tracks: List[str] = []
    road_items = row.get("取得できるスキル/アイテム", "") or ""
    
    # Try different separators
    separators = ["；", "/", " / "]
    items = []
    for sep in separators:
        if sep in road_items:
            items = road_items.split(sep)
            break
    else:
        items = [road_items] if road_items else []
    
    # Check if this is the アンビバレンス HiMERU card
    card_name = row.get("卡面名称", "")
    is_ambivalence_himeru = "裏表アンビバレンス" in card_name and "HiMERU" in card_name
    
    for it in items:
        it = it.strip()
        if not it:
            continue
        
        # Extract MV costume names - look for specific costume names in quotes
        if "MV衣装" in it:
            if "「" in it and "」" in it:
                # Extract costume name from quotes: MV衣装「アンビバレンス衣装」
                costume_match = re.search(r"MV衣装「([^」]+)」", it)
                if costume_match:
                    costume_name = costume_match.group(1)
                    # Special handling for アンビバレンス HiMERU card
                    if is_ambivalence_himeru:
                        # Only keep the base アンビバレンス衣装, not variants
                        if costume_name == "アンビバレンス衣装":
                            if costume_name not in mv_items:
                                mv_items.append(costume_name)
                    else:
                        if costume_name not in mv_items:
                            mv_items.append(costume_name)
            elif not ("一覧" in it or "リンク" in it or "あり" in it or "付き" in it or "プレゼント" in it or "ピース" in it):
                # Only include if it's not a generic description or costume piece
                if not is_ambivalence_himeru:  # Skip for special case
                    mv_items.append(it)
        
        # Extract room costume names
        elif "ルーム衣装" in it or "房间衣装" in it:
            if "「" in it and "」" in it:
                # Extract costume name from quotes
                costume_match = re.search(r"(?:ルーム衣装|房间衣装)「([^」]+)」", it)
                if costume_match:
                    costume_name = costume_match.group(1)
                    if costume_name not in room_items:
                        room_items.append(costume_name)
            elif not ("一覧" in it or "リンク" in it or "あり" in it):
                room_items.append(it)
        
        # Extract background names
        elif "背景" in it:
            if "「" in it and "」" in it:
                bg_match = re.search(r"背景「([^」]+)」", it)
                if bg_match:
                    bg_name = bg_match.group(1)
                    if bg_name not in bg_items:
                        bg_items.append(bg_name)
            elif not ("一覧" in it or "リンク" in it):
                bg_items.append(it)
        
        # Extract SPP track names
        elif "SPP" in it:
            if "「" in it and "」" in it:
                spp_match = re.search(r"SPP「([^」]+)」", it)
                if spp_match:
                    track_name = spp_match.group(1)
                    if track_name not in spp_tracks:
                        spp_tracks.append(track_name)
            elif not ("一覧" in it or "リンク" in it or "あり" in it) and len(it) > 3:
                spp_tracks.append(it)

    # Special handling for アンビバレンス HiMERU card
    if is_ambivalence_himeru:
        # Ensure both MV and room costumes are アンビバレンス衣装
        if "アンビバレンス衣装" not in mv_items:
            mv_items = ["アンビバレンス衣装"]
        else:
            mv_items = ["アンビバレンス衣装"]  # Only keep the base costume
        
        if "アンビバレンス衣装" not in room_items:
            room_items = ["アンビバレンス衣装"]

    # Card name with star suffix
    name = row.get("卡面名称", "")
    rarity = (row.get("レアリティ", "") or "").strip()
    if rarity and not rarity.startswith("☆"):
        # Normalize e.g. '5' -> '☆5'
        if re.match(r"^\d+$", rarity):
            rarity = f"☆{rarity}"
    if name and rarity:
        name = f"{name} {rarity}"

    # Set the status indicator for 5-star cards
    status_indicator = ""
    if use_initial_stats:
        status_indicator = "一卡"
    else:
        # Check if this could be a 5-star card that would have dual rows
        if is_5_star:
            status_indicator = "满破"

    # For 3-star cards, hide center技能, live技能(lv5), support技能(lv3)
    center_skill = "" if is_3_star else row.get("センタースキル 効果", "")
    live_skill_lv5 = "" if is_3_star else live_lv5
    support_skill_lv3 = "" if is_3_star else sup_lv3

    # Optimize MV costume selection: prefer main costume over variants
    if mv_items:
        # Look for main costume (without parentheses or special markers)
        main_costumes = []
        for costume in mv_items:
            # Prefer costumes without parentheses (main versions)
            if "（" not in costume and ")" not in costume:
                main_costumes.append(costume)
        
        # If we found main costumes, use only the first one
        if main_costumes:
            mv_items = [main_costumes[0]]
    
    # If no room costumes found but MV costumes exist, use MV costumes as room costumes
    final_room_items = room_items if room_items else mv_items
    
    mapped = {
        "卡面名称": name,
        "活动名称": row.get("活动名称", ""),
        "center技能名称": row.get("センタースキル 名称", ""),
        "live技能名": row.get("ライブスキル 名称", ""),
        "support技能名": row.get("サポートスキル 名称", ""),
        "Unnamed: 4": status_indicator,
        "DA": pick_stat("Da"),
        "VO": pick_stat("Vo"),
        "PF": pick_stat("Pf"),
        "综合值": pick_stat("総合値"),
        "center技能": center_skill,
        "live技能（lv5）": live_skill_lv5,
        "support技能（lv3）": support_skill_lv3,
        "MV衣装": " / ".join(mv_items),
        "房间衣装": " / ".join(final_room_items),
        "背景": " / ".join(bg_items),
        "spp对应乐曲": " / ".join(spp_tracks),
        "故事": "",
    }
    # Preserve order: only include known columns; missing -> empty
    return {col: mapped.get(col, "") for col in columns_order}


def write_excel_rows(out_path: str, rows: List[Dict[str, str]], columns_order: List[str]) -> None:
    normalized = [{col: r.get(col, "") for col in columns_order} for r in rows]
    df = pd.DataFrame(normalized, columns=columns_order)
    df.to_excel(out_path, index=False)


def main() -> None:
    # Accept URL from argv or stdin, default to yearly event directory
    if len(sys.argv) > 1 and sys.argv[1].strip():
        url = sys.argv[1].strip()
    else:
        default_url = "https://gamerch.com/ensemble-star-music/895943"
        print(f"请输入卡面页面链接（直接回车使用默认年间イベント页面: {default_url} ）:")
        url = input().strip()
        if not url:
            url = default_url
            print(f"使用默认链接: {url}")
    
    # 检查命令行参数以确定运行模式
    use_multithreading = True  # 默认使用多线程
    max_workers = 8  # 默认线程数
    
    # 解析命令行参数
    if len(sys.argv) > 2:
        for arg in sys.argv[2:]:
            if arg == "--single-thread":
                use_multithreading = False
            elif arg.startswith("--threads="):
                try:
                    max_workers = int(arg.split("=")[1])
                    max_workers = max(1, min(max_workers, 16))  # 限制在1-16之间
                except ValueError:
                    max_workers = 8
    
    # 如果没有命令行参数，则询问用户
    if len(sys.argv) <= 2:
        print("\n选择爬取模式:")
        print("1. 单线程模式（稳定，较慢）")
        print("2. 多线程模式（快速，推荐）")
        mode_choice = input("请选择模式 (1/2，默认为2): ").strip()
        use_multithreading = mode_choice != "1"
        
        if use_multithreading:
            max_workers_input = input("请输入线程数 (默认为8): ").strip()
            try:
                max_workers = int(max_workers_input) if max_workers_input else 8
                max_workers = max(1, min(max_workers, 16))  # 限制在1-16之间
            except ValueError:
                max_workers = 8
    
    if use_multithreading:
        print(f"使用多线程模式，线程数: {max_workers}")
    else:
        print("使用单线程模式")
    
    try:
        html, md = crawl_page(url)
    except Exception as e:
        print(f"抓取失败: {e}")
        return

    soup = BeautifulSoup(html, "lxml")
    # Detect whether current page is a card detail page (with bracketed title)
    preview_name = parse_card_name(html)
    full_text = soup.get_text("\n", strip=True)
    
    # Check if this is a yearly event directory page
    is_directory = "年間イベント" in full_text or "イベント一覧" in full_text or "/895943" in url
    
    # Prefer text-based detection: treat as listing when typical markers are present
    has_scout_section = any(k in full_text for k in ["スカウト追加カード", "追加カード", "スカウトの確率について", "クロススカウト・"])
    # Detail page heuristic: only if no listing markers AND has bracketed card title
    is_detail = not has_scout_section and not is_directory and bool(re.search(r"\uFF3B[^\uFF3D]+\uFF3D", preview_name))
    
    # Try to collect detail links
    links = []
    if is_detail:
        links = []
    elif is_directory:
        # Extract card links from directory page for target dates
        print("检测到目录页面，提取目标日期的卡面链接...")
        links = extract_cards_from_directory(html, url)
    else:
        # Regular listing page
        links = find_card_links(soup, url)
    

    
    rows: List[Dict[str, str]] = []
    
    # Handle different page types
    if is_directory:
        # Directory page: process all found card-event pairs
        print(f"处理目录页面，找到 {len(links)} 个卡面链接")
        
        if use_multithreading:
            # 使用多线程模式处理目录页面 - 完整详情提取
            print(f"使用多线程模式处理 {len(links)} 个卡面的完整详情...")
            
            # 创建多线程获取器
            fetcher = MultiThreadedCardFetcher(
                max_workers=max_workers,
                timeout=15,
                delay=0.1  # 100ms延迟避免过于频繁的请求
            )
            
            # 使用新的批量完整详情提取功能
            print("正在批量获取卡面完整详情...")
            card_details_list = fetcher.fetch_card_full_details_batch(links)
            
            # 将结果添加到rows
            rows.extend(card_details_list)
            
            print(f"多线程处理完成，成功提取 {len(card_details_list)} 个卡面的完整详情")
        else:
            # 使用单线程模式处理目录页面（原有逻辑）
            for i, (card_url, event_name) in enumerate(links):
                try:
                    print(f"  处理链接 {i+1}/{len(links)}: {card_url} (活动: {event_name})")
                    h, _ = crawl_page(card_url)
                    sp = BeautifulSoup(h, "lxml")
                    card_name = parse_card_name(h)
                    
                    # Skip profile pages and non-card pages
                    if "プロフィール" in card_name or "詳細" in card_name:
                        print(f"    跳过非卡面页面: {card_name}")
                        continue
                    
                    # Check if this is a valid card page with bracketed name
                    if not re.search(r"［[^］]+］", card_name):
                        print(f"    跳过无效卡面: {card_name}")
                        continue
                    
                    # Extract detailed information
                    basic = extract_basic_info(sp)
                    status = extract_status(sp)
                    skills = extract_skills(sp)
                    road_items = extract_road_items(sp)
                    
                    row = build_row(card_name, basic, status, skills, road_items)
                    row["活动名称"] = event_name  # Use extracted event name
                    
                    rows.append(row)
                    print(f"    成功提取卡面: {card_name} (活动: {event_name})")
                except Exception as e:
                    print(f"    处理链接失败: {card_url} - {e}")
                    continue
    
    elif not is_detail:
        # Regular listing page
        base_rows = extract_additional_cards_from_listing(soup)
        target_names = [r.get("卡面名称", "") for r in base_rows]
        event_name = base_rows[0].get("イベント名", "") if base_rows else ""
        
        # If we have links, try to match them with base rows for better targeting
        if links and base_rows:
            print(f"找到 {len(links)} 个详情链接，尝试匹配 {len(base_rows)} 个基础卡面")
            target_names = [r.get("卡面名称", "") for r in base_rows]
            matched_count = 0
            
            for link in links:
                if matched_count >= len(base_rows):
                    break
                try:
                    h, _ = crawl_page(link)
                    sp = BeautifulSoup(h, "lxml")
                    card_name = parse_card_name(h)
                    
                    # Skip profile pages and non-card pages
                    if "プロフィール" in card_name or "詳細" in card_name:
                        print(f"  跳过非卡面页面: {card_name}")
                        continue
                    
                    # Check if this is a valid card page with bracketed name
                    if not re.search(r"［[^］]+］", card_name):
                        print(f"  跳过无效卡面: {card_name}")
                        continue
                    
                    # Extract detailed information
                    basic = extract_basic_info(sp)
                    status = extract_status(sp)
                    skills = extract_skills(sp)
                    road_items = extract_road_items(sp)
                    

                    
                    row = build_row(card_name, basic, status, skills, road_items)
                    row["イベント名"] = event_name
                    
                    # Match with base row for rarity by finding the best character name match
                    best_match_rarity = ""
                    for br in base_rows:
                        base_name = br.get("卡面名称", "")
                        # Extract character name from both card names for comparison
                        card_char = re.search(r"］([^☆\s]+)", card_name)
                        base_char = re.search(r"］([^☆\s]+)", base_name) if base_name else None
                        
                        if card_char and base_char:
                            if card_char.group(1).strip() == base_char.group(1).strip():
                                best_match_rarity = br.get("レアリティ", "")
                                break
                        # Fallback: check if any significant part of base name appears in card name
                        elif base_name and any(part in card_name for part in base_name.split() if len(part) > 1):
                            best_match_rarity = br.get("レアリティ", "")
                            break
                    
                    if best_match_rarity:
                        row["レアリティ"] = best_match_rarity
                    
                    rows.append(row)
                    matched_count += 1
                    print(f"  匹配卡面 {matched_count}: {card_name}")
                except Exception as e:
                    print(f"  处理链接失败: {link} - {e}")
                    continue
        
        # If we couldn't find detail links but have base rows, use them directly
        elif not links and base_rows:
            print(f"未找到详情页链接，使用列表页基础数据（{len(base_rows)}个卡面）")
            for br in base_rows:
                row = {
                    "卡面名称": br.get("卡面名称", ""),
                    "レアリティ": br.get("レアリティ", ""),
                    "イベント名": br.get("イベント名", ""),
                    # Fill other fields with empty values
                    "タイプ/属性": "",
                    "ファン上限": "",
                    "追加日": "",
                    "Da": "", "Vo": "", "Pf": "",
                    "センタースキル": "",
                    "ライブスキル": "",
                    "サポートスキル": "",
                    "取得できるスキル/アイテム": "",
                }
                rows.append(row)
    
    if rows:
        # Already parsed from listing + detail matching
        pass
    else:
        # Fallback: single card page
        print("检测到卡面详情页，正在解析……")
        card_name = parse_card_name(html)
        basic = extract_basic_info(soup)
        status = extract_status(soup)
        skills = extract_skills(soup)
        road_items = extract_road_items(soup)
        row = build_row(card_name, basic, status, skills, road_items)
        add = row.get("追加日", "")
        m_event = re.search(r"追加日[^\n]*（([^）]+)）", add)
        if m_event:
            row["イベント名"] = m_event.group(1).strip()
        rows.append(row)

    # Load template columns order
    base_dir = os.path.dirname(os.path.dirname(__file__))
    template_path = os.path.join(base_dir, "es2 卡面名称及技能一览（新表）示例.xlsx")
    try:
        tmpl_df = pd.read_excel(template_path)
        columns_order = tmpl_df.columns.tolist()
        # 确保活动名称列被包含，如果不存在则添加到卡面名称后面
        if "活动名称" not in columns_order:
            if "卡面名称" in columns_order:
                idx = columns_order.index("卡面名称") + 1
                columns_order.insert(idx, "活动名称")
            else:
                columns_order.insert(1, "活动名称")
        print(f"使用模板列顺序（已添加活动名称列）: {columns_order}")
    except Exception as e:
        print(f"无法加载模板文件: {e}")
        # 使用示例文件的确切列顺序
        columns_order = [
            "卡面名称", "活动名称", "center技能名称", "live技能名", "support技能名", "Unnamed",
            "DA", "VO", "PF", "综合值", "center技能", "live技能（lv5）", "support技能（lv3）",
            "MV衣装", "房间衣装", "背景", "spp对应乐曲", "故事"
        ]

    # Timestamped output filename
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_name = f"es2 卡面名称及技能一览{ts}.xlsx"
    out_path = os.path.join(base_dir, out_name)
    
    # Map rows to template format with special handling for 5-star cards
    final_rows: List[Dict[str, str]] = []
    if rows and columns_order:
        for r in rows:
            # Check if this is a 5-star card
            rarity = r.get("レアリティ", "").strip()
            card_name = r.get("卡面名称", "")
            is_5_star = rarity == "☆5" or "☆5" in card_name or "★5" in card_name
            
            if is_5_star:
                # Create two rows for 5-star cards: initial stats and max stats
                # Row 1: Initial stats (一卡)
                initial_row = map_to_template(r, columns_order, use_initial_stats=True)
                final_rows.append(initial_row)
                
                # Row 2: Max stats (満破)
                max_row = map_to_template(r, columns_order, use_initial_stats=False)
                final_rows.append(max_row)
            else:
                # Single row for non-5-star cards
                final_rows.append(map_to_template(r, columns_order))
    else:
        final_rows = rows
    
    write_excel_rows(out_path, final_rows, columns_order)
    print(f"已输出: {out_path}")


def extract_cards_with_multithreaded_details(html: str, base_url: str, 
                                           max_workers: int = 8, 
                                           fetch_details: bool = True) -> List[Tuple[str, str, str]]:
    """
    提取卡面并使用多线程获取详细信息
    
    Args:
        html: 页面HTML内容
        base_url: 基础URL
        max_workers: 最大工作线程数
        fetch_details: 是否获取卡面详情（卡面名称）
        
    Returns:
        List[Tuple[card_url, event_name, card_name]] - 卡面URL、活动名、卡面名称的列表
    """
    
    print("=== 使用多线程提取卡面详情 ===")
    
    # 首先提取卡面URL和活动名
    card_event_pairs = extract_cards_from_directory(html, base_url)
    
    if not card_event_pairs:
        print("未找到任何卡面")
        return []
    
    print(f"找到 {len(card_event_pairs)} 个卡面，准备获取详情...")
    
    if not fetch_details:
        # 如果不需要获取详情，直接返回URL和活动名，卡面名称为空
        return [(url, event, "") for url, event in card_event_pairs]
    
    # 提取所有卡面URL
    card_urls = [url for url, _ in card_event_pairs]
    
    # 创建多线程获取器
    fetcher = MultiThreadedCardFetcher(
        max_workers=max_workers,
        timeout=15,
        delay=0.1  # 100ms延迟避免过于频繁的请求
    )
    
    # 批量获取卡面详情
    card_details = fetcher.fetch_card_details_batch(card_urls)
    
    # 组合结果
    results = []
    for card_url, event_name in card_event_pairs:
        if card_url in card_details:
            card_name, status = card_details[card_url]
            results.append((card_url, event_name, card_name))
        else:
            results.append((card_url, event_name, "获取失败"))
    
    return results


def crawl_and_extract_with_multithreading(url: str, max_workers: int = 8) -> List[Tuple[str, str, str]]:
    """
    爬取页面并使用多线程提取卡面详情
    
    Args:
        url: 目标URL
        max_workers: 最大工作线程数
        
    Returns:
        List[Tuple[card_url, event_name, card_name]] - 卡面信息列表
    """
    
    print(f"开始爬取页面: {url}")
    
    try:
        # 爬取页面
        html, _ = crawl_page(url)
        
        # 使用多线程提取卡面详情
        results = extract_cards_with_multithreaded_details(html, url, max_workers)
        
        print(f"\n=== 最终结果 ===")
        print(f"成功提取 {len(results)} 个卡面的详细信息")
        
        # 按活动分组统计
        event_stats = {}
        for _, event_name, card_name in results:
            if event_name not in event_stats:
                event_stats[event_name] = []
            event_stats[event_name].append(card_name)
        
        print(f"\n=== 按活动统计 ===")
        for event_name, cards in event_stats.items():
            print(f"{event_name}: {len(cards)} 个卡面")
        
        return results
        
    except Exception as e:
        print(f"爬取失败: {e}")
        return []


if __name__ == "__main__":
    main()