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
    """
    爬取指定URL的页面内容，优先使用Crawl4AI，失败时回退到requests。
    
    功能说明：
    - 优先尝试使用 Crawl4AI 进行页面爬取，支持 JavaScript 渲染的动态页面
    - 如果 Crawl4AI 不可用或失败，则回退到传统的 requests 方式
    - 返回页面的 HTML 内容和 Markdown 格式（如果可用）
    
    参数：
    - url: 要爬取的页面URL
    
    返回：
    - Tuple[str, str]: (HTML内容, Markdown内容)，Markdown可能为空字符串
    
    异常处理：
    - Crawl4AI 异常时自动回退到 requests
    - requests 异常会向上抛出，由调用方处理
    """
    # 优先使用 Crawl4AI（支持 JavaScript 渲染）
    if HAS_CRAWL4AI:
        try:
            # 配置无头浏览器
            browser_cfg = BrowserConfig(headless=True)
            crawler = WebCrawler(browser_config=browser_cfg)
            # 最小配置，允许 JavaScript 执行以处理动态页面
            crawl_cfg = CrawlConfig()
            result = crawler.crawl(url=url, config=crawl_cfg)
            html = result.html or ""
            md = getattr(result, "markdown", "") or ""
            # 如果成功获取到HTML内容，返回结果
            if html.strip():
                return html, md
        except Exception:
            # Crawl4AI 失败时静默回退到 requests
            pass

    # 回退方案：使用 requests 进行传统HTTP请求
    headers = {
        # 模拟真实浏览器的请求头，避免被反爬虫机制拦截
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "ja,en-US;q=0.7,en;q=0.3",  # 优先日语，适合日本网站
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }
    import time
    time.sleep(1)  # 添加延迟避免触发频率限制
    resp = requests.get(url, headers=headers, timeout=20, verify=False)
    resp.raise_for_status()  # 如果HTTP状态码表示错误，抛出异常
    return resp.text, ""  # 返回HTML内容，Markdown为空


# 已移除：find_card_links_loose（不在 web 链路中使用）


def find_card_links(soup: BeautifulSoup, base_url: str) -> List[str]:
    """
    从活动页面或列表页面中提取卡面详情页链接。
    
    功能说明：
    - 使用多重启发式策略从页面中识别和提取卡面详情页链接
    - 优先在"追加カード"区域查找，然后在卡面展示区域查找
    - 通过URL模式和链接文本格式进行双重验证
    
    提取策略：
    1. 查找包含"追加カード"的标题区域，在其后续兄弟元素中搜索链接
    2. 在卡面展示区域查找包含全角括号格式［...］的卡面名称链接
    3. 验证链接URL包含'/ensemble-star-music/<数字>'模式
    4. 排除当前页面自身的链接，避免循环引用
    
    参数：
    - soup: 已解析的页面BeautifulSoup对象
    - base_url: 当前页面的基础URL，用于排除自引用
    
    返回：
    - List[str]: 去重后的卡面详情页URL列表，最多返回10个链接
    
    注意：
    - 限制返回数量避免过长的处理时间
    - 保持链接顺序，优先返回页面中较早出现的链接
    """
    urls: List[str] = []
    # 从基础URL中提取ID，用于排除自引用
    base_id = re.search(r"ensemble-star-music/(\d+)", base_url)
    base_id_str = base_id.group(1) if base_id else None

    # 策略1：查找"追加カード"区域中的卡面链接
    section = soup.find(lambda t: t.name in {"h2", "h3", "div", "section"} and "追加カード" in t.get_text("\n", strip=True))
    anchors: List[Tuple[str, str]] = []
    
    if section:
        # 在"追加カード"标题后的兄弟元素中查找链接
        cur = section
        for _ in range(20):  # 限制搜索范围，避免过度遍历
            cur = cur.find_next_sibling()
            if not cur:
                break
            txt = cur.get_text("\n", strip=True)
            # 遇到下一个主要区域时停止搜索
            if any(k in txt for k in ["ボーナス効果", "スカウトの確率について", "SCRカラーについて"]):
                break
            # 收集当前元素中的所有链接
            for a in cur.find_all('a', href=True):
                anchors.append((a['href'], a.get_text(strip=True)))
    
    # 策略2：在卡面展示区域查找直接链接
    card_display_area = soup.find('div', class_=lambda x: x and 'card' in x.lower()) or soup
    for a in card_display_area.find_all('a', href=True):
        text = a.get_text(strip=True)
        # 查找包含全角括号格式的卡面名称链接
        if re.search(r"\uFF3B[^\uFF3D]+\uFF3D", text):
            anchors.append((a['href'], text))

    # 验证和过滤链接
    for href, text in anchors:
        # 必须包含ensemble-star-music路径
        if 'ensemble-star-music/' not in href:
            continue
        # 提取URL中的数字ID
        m = re.search(r"ensemble-star-music/(\d+)", href)
        if not m:
            continue
        card_id = m.group(1)
        # 排除空ID或与当前页面相同的ID
        if not card_id or card_id == base_id_str:
            continue
        
        # 验证链接文本包含全角括号格式的卡面名称
        has_bracket = re.search(r"\uFF3B[^\uFF3D]+\uFF3D", text)
        
        if not has_bracket:
            continue
            
        # 规范化为绝对URL
        if href.startswith('http'):
            urls.append(href)
        else:
            urls.append('https://gamerch.com/' + href.lstrip('/'))
    
    # 去重并保持顺序，限制返回数量以优化性能
    seen = set()
    dedup: List[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            dedup.append(u)
            if len(dedup) >= 10:  # 限制最多10个链接，避免过长处理时间
                break
    return dedup


def parse_card_name(html: str) -> str:
    """
    从页面HTML中解析并提取卡面名称。
    
    功能说明：
    - 使用多级回退策略从不同位置提取卡面名称
    - 优先使用Open Graph标签，然后是H1标题，最后是页面标题
    - 对包含全角括号格式的卡面名称进行特殊处理和规范化
    
    提取优先级：
    1. og:title meta标签（最准确，通常包含完整卡面信息）
    2. H1标题元素（页面主标题）
    3. HTML title标签（页面标题，作为最后备选）
    
    参数：
    - html: 页面的HTML内容字符串
    
    返回：
    - str: 解析得到的卡面名称，如果无法解析则返回空字符串
    
    名称格式处理：
    - 识别并规范化全角括号格式：［卡面类型］角色名
    - 去除多余的分隔符和空白字符
    - 保持原始的日文格式
    """
    soup = BeautifulSoup(html, "lxml")
    
    # 优先策略：使用Open Graph标题（最准确）
    og = soup.find("meta", attrs={"property": "og:title"})
    if og and og.get("content"):
        title = og["content"].strip()
        # 尝试提取全角括号格式的卡面名称：［...］ 名称
        m = re.search(r"\uFF3B([^\uFF3D]+)\uFF3D\s*([^\-|]+)", title)  # ［...］ Name
        if m:
            # 规范化格式：［卡面类型］角色名
            return f"［{m.group(1).strip()}］{m.group(2).strip()}"
        return title
    
    # 回退策略1：使用H1标题元素
    h1 = soup.find("h1")
    if h1:
        return h1.get_text(strip=True)
    
    # 回退策略2：使用页面title标签（最后备选）
    if soup.title and soup.title.string:
        t = soup.title.string.strip()
        # 同样尝试提取全角括号格式
        m = re.search(r"\uFF3B([^\uFF3D]+)\uFF3D\s*([^\-|]+)", t)
        if m:
            return f"［{m.group(1).strip()}］{m.group(2).strip()}"
        return t
    
    # 无法解析时返回空字符串
    return ""


def extract_cards_from_directory(html: str, base_url: str) -> List[Tuple[str, str]]:
    """
    从年度活动目录页面提取特定日期的卡面详情链接和活动名称。
    
    功能说明：
    - 针对特定目标日期（10日、14日、15日、25日、月末等）提取卡面信息
    - 使用双重策略：优先从标题区域提取，回退到表格/容器中查找
    - 动态提取实际活动名称，而非使用固定模板
    - 支持全年度日期覆盖（2024年1月-12月）
    
    目标日期策略：
    - 重点日期：10日、14日、15日、25日
    - 月末日期：30日/31日（根据月份调整）
    - 月末前一日：29日/30日（避免遗漏）
    
    提取策略：
    1. 标题策略：查找包含日期的H2/H3标题，提取其下方的卡面链接
    2. 容器策略：在表格单元格或div容器中查找日期和相关卡面
    3. 活动名动态提取：从上下文中识别实际活动名称
    
    参数：
    - html: 年度目录页面的HTML内容
    - base_url: 基础URL（用于链接规范化）
    
    返回：
    - List[Tuple[str, str]]: (卡面URL, 活动名称) 元组列表
    
    卡面识别条件：
    - URL包含 'ensemble-star-music/' 且以数字结尾
    - 文本以全角括号开头：［...］
    - 排除列表页面（包含'一覧'或'カード一覧'）
    - 卡面名称长度合理（>10字符）
    """
    soup = BeautifulSoup(html, "lxml")
    
    def is_target_date(day: int, month: int) -> bool:
        """
        检查给定日期是否为目标提取日期。
        
        目标日期包括：
        - 固定重点日期：10日、14日、15日、25日
        - 月末及月末前一日（根据月份天数调整）
        """
        # 固定的重点日期
        if day in [10, 14, 15, 25]:
            return True
        
        # 根据月份检查月末和月末前一日
        if month in [1, 3, 5, 7, 8, 10, 12]:  # 31天的月份
            return day in [30, 31]
        elif month in [4, 6, 9, 11]:  # 30天的月份
            return day in [29, 30]
        elif month == 2:  # 2月（假设非闰年）
            return day in [27, 28]
        return False
    
    def find_cards_by_date_with_dynamic_event_names(date_pattern: str) -> List[Tuple[str, str]]:
        """
        根据日期模式查找卡面链接并动态提取实际活动名称。
        
        使用双重策略：
        1. 标题策略：在H2/H3标题中查找日期，提取标题下方的卡面
        2. 容器策略：在表格或div容器中查找日期和相关卡面
        """
        cards = []
        
        # 策略1：在H2/H3标题中查找包含日期模式的标题
        headers = soup.find_all(['h2', 'h3'], string=re.compile(date_pattern))
        
        print(f"  查找日期模式 '{date_pattern}': 在标题中找到 {len(headers)} 个匹配")
        
        for header in headers:
            header_text = header.get_text(strip=True)
            print(f"    标题: {header_text}")
            
            # 从标题文本中提取实际活动名称
            actual_event_name = extract_event_name_from_context(header_text, date_pattern)
            
            # 遍历标题后的兄弟元素，直到遇到下一个同级或更高级标题
            current = header.next_sibling
            section_cards = []
            
            while current:
                # 如果遇到同级或更高级标题则停止
                if (hasattr(current, 'name') and 
                    current.name in ['h1', 'h2', 'h3'] and 
                    current != header):
                    break
                
                # 在当前元素中查找卡面链接
                if hasattr(current, 'find_all'):
                    card_links = current.find_all('a', href=True)
                    
                    for link in card_links:
                        href = link.get('href', '')
                        text = link.get_text(strip=True)
                        
                        # 检查是否为有效的卡面链接
                        if ('ensemble-star-music/' in href and 
                            re.search(r'/\d+$', href) and 
                            text.startswith('［') and '］' in text and
                            len(text) > 10 and  # 卡面名称通常较长
                            not text.endswith('一覧') and  # 排除列表页面
                            'カード一覧' not in text):  # 排除卡面一览页面
                            
                            # 规范化URL格式
                            if href.startswith('http'):
                                card_url = href
                            else:
                                card_url = 'https://gamerch.com' + href.lstrip('/')
                            
                            section_cards.append((card_url, actual_event_name, text))
                
                current = current.next_sibling
            
            # 将找到的卡面及其实际活动名称添加到结果中
            for card_url, event_name, card_text in section_cards:
                cards.append((card_url, event_name))
            
            if section_cards:
                print(f"    在标题 '{actual_event_name}' 区域找到 {len(section_cards)} 个卡面")
        
        # 策略2：如果在标题中未找到，则在表格单元格或div中查找
        if not cards:
            print(f"  未在标题中找到，尝试在表格和div中查找...")
            
            # 查找所有包含日期的元素
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
        if 'Halloween' in context_text or 'Witchcraft' in context_text:
            print(f"    回退到Witchcraft Halloween Event")
            return f"{simple_date}　Witchcraft Halloween Event"
        elif 'DI:Verse' in context_text:
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
    all_links = soup.find_all('a', href=True)
    seen_urls = {u for u, _ in unique_pairs}
    extra_pairs = []
    for link in all_links:
        href = link.get('href', '')
        text = link.get_text(strip=True)
        if ('ensemble-star-music/' in href and
            re.search(r'/\d+$', href) and
            text.startswith('［') and '］' in text and
            len(text) > 10 and
            '一覧' not in text and
            'カード一覧' not in text):
            if href.startswith('http'):
                card_url = href
            else:
                card_url = 'https://gamerch.com' + href.lstrip('/')
            if card_url in seen_urls:
                continue
            event_name = ''
            header = None
            p = link
            for _ in range(50):
                if hasattr(p, 'previous_sibling') and p.previous_sibling:
                    p = p.previous_sibling
                elif hasattr(p, 'parent') and p.parent:
                    p = p.parent
                else:
                    break
                if hasattr(p, 'name') and p.name in ['h2', 'h3']:
                    header = p
                    break
            if header:
                ht = header.get_text(strip=True)
                m = re.search(r'(\d{1,2})月(\d{1,2})日', ht)
                if m:
                    simple_date = f"{int(m.group(1)):02d}月{int(m.group(2)):02d}日"
                    event_name = extract_event_name_from_context(ht, simple_date)
            if not event_name:
                container_text = link.parent.get_text(strip=True) if hasattr(link, 'parent') else ''
                m2 = re.search(r'(\d{1,2})月(\d{1,2})日', container_text)
                if m2:
                    simple_date2 = f"{int(m2.group(1)):02d}月{int(m2.group(2)):02d}日"
                    event_name = extract_event_name_from_context(container_text, simple_date2)
            if not event_name:
                event_name = '未知活动'
            extra_pairs.append((card_url, event_name))
            seen_urls.add(card_url)
    if extra_pairs:
        print(f"额外发现 {len(extra_pairs)} 个卡面详情链接")
        unique_pairs.extend(extra_pairs)
    return unique_pairs


def extract_event_name_from_listing(soup: BeautifulSoup) -> str:
    """Extract the event/scout name from listing page.
    Priority:
    1) Text containing 'クロススカウト・' and '／inspired' or '／empathy'
    2) Text containing 'クロススカウト・' and other patterns like '／SIGEL', '／ALKALOID', etc.
    3) Any text containing 'アンビバレンス' with 'クロススカウト'
    4) Page title stripped of site prefix like '【あんスタMusic】'
    """
    full_text = soup.get_text("\n", strip=True)
    # 1) Explicit inspired/empathy (original patterns)
    m = re.search(r"(クロススカウト・[^\n／]+／(?:inspired|empathy))", full_text)
    if m:
        return m.group(1).strip()
    # 2) Extended patterns for other unit names like SIGEL, ALKALOID, etc.
    m = re.search(r"(クロススカウト・[^\n／]+／[A-Z]+)", full_text)
    if m:
        return m.group(1).strip()
    # 3) クロススカウト＋アンビバレンス
    m = re.search(r"(クロススカウト・[^\n]*アンビバレンス[^\n]*)", full_text)
    if m:
        return m.group(1).strip()
    # 4) Title fallback
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
    """
    从卡面详情页面提取基本信息。
    
    功能说明：
    - 提取卡面的稀有度、类型/属性、粉丝上限、追加日期等基础信息
    - 使用多重策略：优先从"基本情報"区块提取，回退到全页面文本搜索
    - 支持表格式和文本式两种信息布局
    
    提取策略：
    1. 区块策略：查找包含"基本情報"的标题区块及其后续内容
    2. 标签策略：通过标签-值对的形式提取信息
    3. 正则策略：使用正则表达式从文本中匹配特定格式的信息
    
    参数：
    - soup: 卡面详情页面的BeautifulSoup对象
    
    返回：
    - Dict[str, str]: 包含基本信息的字典，键为日文字段名
    
    提取字段：
    - レアリティ: 稀有度（如☆5、☆4等）
    - タイプ/属性: 卡面类型和属性
    - ファン上限: 粉丝数量上限
    - 追加日: 卡面添加到游戏的日期
    """
    info = {
        "レアリティ": "",
        "タイプ/属性": "",
        "ファン上限": "",
        "追加日": "",
    }
    # 查找包含"基本情報"的区块
    block = soup.find(lambda t: t.name in {"h2", "h3", "div", "section"} and "基本情報" in t.get_text("\n", strip=True))
    text = ""
    if block:
        # 收集区块及其后续兄弟元素的内容
        texts = [block.get_text("\n", strip=True)]
        sib = block.find_next_sibling()
        for _ in range(5):
            if not sib:
                break
            texts.append(sib.get_text("\n", strip=True))
            sib = sib.find_next_sibling()
        text = "\n".join(texts)
    else:
        # 回退到全页面文本搜索
        text = soup.get_text("\n", strip=True)

    # 尝试表格式标签-值提取
    def find_label(label: str) -> str:
        """查找指定标签对应的值"""
        tag = soup.find(string=re.compile(label))
        if tag:
            parent = getattr(tag, 'parent', None)
            if parent:
                # 同行值提取
                full = parent.get_text("\n", strip=True)
                m = re.search(label + r"\s*([^\n]+)", full)
                if m:
                    return m.group(1).strip()
                # 下一个兄弟元素值提取
                for sib in parent.find_next_siblings():
                    val = sib.get_text("\n", strip=True)
                    if val:
                        return val
        return ""

    # 使用标签查找函数提取各字段
    info["レアリティ"] = info["レアリティ"] or find_label("レアリティ")
    info["タイプ/属性"] = info["タイプ/属性"] or find_label("タイプ/属性")
    info["ファン上限"] = info["ファン上限"] or find_label("ファン上限")
    info["追加日"] = info["追加日"] or find_label("追加日")

    # 使用正则表达式进行简单提取（作为备选方案）
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
    """
    从卡面详情页面提取状态数值表格。
    
    功能说明：
    - 提取卡面的各种状态数值（总合值、Da、Vo、Pf）
    - 支持多个状态阶段：初期值、无凸MAX值、完凸MAX值
    - 自动识别表格结构并解析列标题和行标题
    
    数据结构：
    - status[列][行] = 值
    - 例如：status['初期値']['総合値'] = '23510'
    
    参数：
    - soup: 卡面详情页面的BeautifulSoup对象
    
    返回：
    - Dict[str, Dict[str, str]]: 嵌套字典，外层键为状态阶段，内层键为状态类型
    
    状态类型：
    - 総合値: 总合数值
    - Da: Dance数值
    - Vo: Vocal数值  
    - Pf: Performance数值
    """
    # status[列][行] = 値  e.g., status['初期値']['総合値'] = '23510'
    status: Dict[str, Dict[str, str]] = {}
    # 查找包含状态数值的目标表格
    target_table = None
    for table in soup.find_all("table"):
        t = table.get_text("\n", strip=True)
        if all(k in t for k in ["総合値", "Da", "Vo", "Pf"]):
            target_table = table
            break
    if not target_table:
        return status

    # 提取列标题（初期値 / 無凸MAX値 / 完凸MAX値）
    columns: List[str] = []
    for tr in target_table.find_all("tr"):
        cells = [c.get_text(strip=True) for c in tr.find_all(["th", "td"])]
        if any(x in cells for x in ["初期値", "無凸MAX値", "完凸MAX値"]):
            # 第一个单元格通常是行标题占位符
            if len(cells) >= 2:
                columns = [c for c in cells[1:] if c]
            break
    if not columns:
        columns = ["初期値", "無凸MAX値", "完凸MAX値"]

    def as_num(s: str) -> str:
        """数值格式化：移除逗号、横线并去除空格"""
        s = s.replace(",", "").replace("-", "").strip()
        return s

    # 遍历表格行，提取状态数值
    for tr in target_table.find_all("tr"):
        cells = [c.get_text(strip=True) for c in tr.find_all(["th", "td"])]
        if not cells:
            continue
        row_label = cells[0]
        # 检查是否为目标状态类型
        if row_label in ["総合値", "Da", "Vo", "Pf"]:
            # 将每列的数值填入对应的状态字典
            for idx, col in enumerate(columns):
                if idx + 1 < len(cells):
                    status.setdefault(col, {})[row_label] = as_num(cells[idx + 1])
    return status


def extract_skills(soup: BeautifulSoup) -> Dict[str, Dict[str, str]]:
    """
    从卡面详情页面提取技能信息。
    
    功能说明：
    - 提取中央技能（センタースキル）的名称和效果
    - 提取Live技能（ライブスキル）的名称和效果  
    - 提取支援技能（サポートスキル）的效果
    - 使用多种策略确保技能信息的完整提取
    
    提取策略：
    1. 正则表达式匹配：优先使用模式匹配提取技能名称
    2. 逐行扫描：在正则失败时逐行查找技能信息
    3. 全文搜索：作为最后的备选方案进行上下文搜索
    4. DOM结构解析：通过HTML标签结构定位技能效果
    
    参数：
    - soup: 卡面详情页面的BeautifulSoup对象
    
    返回：
    - Dict[str, Dict[str, str]]: 技能信息字典
      - 外层键：技能类型（センタースキル、ライブスキル、サポートスキル）
      - 内层键：技能属性（名前、効果）
    
    技能类型：
    - センタースキル: 中央技能，包含名前和効果
    - ライブスキル: Live技能，包含名前和効果
    - サポートスキル: 支援技能，仅包含効果
    """
    skills = {
        "センタースキル": {"名称": "", "効果": ""},
        "ライブスキル": {"名称": "", "効果": ""},
        "サポートスキル": {"名称": "", "効果": ""},
    }

    full_text = soup.get_text("\n", strip=True)
    
    # 尽可能缩小到技能部分的文本范围
    section_start = full_text.find("センター/ライブ/サポートスキル")
    skills_text = full_text
    if section_start != -1:
        skills_text = full_text[section_start:]
        # 在下一个主要部分处截断，但保守处理以保留支援技能内容
        for marker in ["アイドルロード", "必要素材数"]:
            idx = skills_text.find(marker)
            if idx != -1:
                skills_text = skills_text[:idx]
                break
        # 只有当スカウト画面距离サポートスキル足够远时才截断
        scout_idx = skills_text.find("スカウト画面")
        support_idx = skills_text.find("サポートスキル")
        if scout_idx != -1 and support_idx != -1 and scout_idx - support_idx > 200:
            skills_text = skills_text[:scout_idx]

    # 中央技能：优先使用明确的名称格式，然后回退到逐行扫描
    center_name = ""
    center_eff = ""

    # 策略1：查找引号格式的中央技能名称
    center_name_match = re.search(r'センタースキル[^「]*「([^」]+)」', skills_text)
    if center_name_match:
        center_name = center_name_match.group(1)
    else:
        # 策略1b：逐行扫描中央技能名称
        lines = skills_text.splitlines()
        for i, line in enumerate(lines):
            line = line.strip()
            if "センタースキル" in line:
                # 查找下一个可能是技能名称的非空行
                for j in range(i + 1, min(i + 4, len(lines))):  # 检查接下来的3行
                    potential_name = lines[j].strip()
                    if (potential_name and 
                        not re.search(r'効果|項目|％|up|UP|固定', potential_name) and
                        len(potential_name) > 2):
                        center_name = potential_name
                        break

        # 策略2：在全页文本中查找已知的技能名称
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
    """
    从卡面详情页面提取アイドルロード（偶像之路）可获得的道具和物品。
    
    功能说明：
    - 提取ルーム衣装（房间服装）、MV衣装、SPP、技能、背景等道具
    - 使用多种策略确保完整提取：正则表达式、DOM结构解析、文本块分析
    - 处理跨行分割的物品名称和特殊格式
    - 自动去重并保持提取顺序
    
    提取策略：
    1. 正则表达式全页搜索：优先使用模式匹配提取各类物品
    2. DOM结构解析：通过HTML标签结构定位物品列表
    3. 文本块分析：在标题间提取物品内容
    4. 逐行扫描：作为最后备选方案进行鲁棒性提取
    
    参数：
    - soup: 卡面详情页面的BeautifulSoup对象
    
    返回：
    - str: 以分号分隔的物品列表字符串
    
    物品类型：
    - ルーム衣装: 房间装饰用服装
    - MV衣装: 音乐视频用服装
    - SPP: 特殊技能点数道具
    - ライブスキル/サポートスキル: 技能道具
    - 背景: 背景装饰物品
    """
    # 首先，始终在整个页面中搜索房间服装和其他物品
    text = soup.get_text("\n", strip=True)
    items: List[str] = []
    
    # 从整个页面提取房间服装（处理多行格式）
    room_costume_matches = re.findall(r"ルーム衣装「([^」]+)」", text)
    for costume in room_costume_matches:
        items.append(f"ルーム衣装「{costume}」")
    
    # 同时处理房间服装跨行分割的情况
    lines = text.splitlines()
    for i, line in enumerate(lines):
        line = line.strip()
        if line == "ルーム衣装" and i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            costume_match = re.match(r"「([^」]+)」", next_line)
            if costume_match:
                costume = costume_match.group(1)
                items.append(f"ルーム衣装「{costume}」")
    
    # 提取MV服装（但不包括促销类型）
    mv_costume_matches = re.findall(r"MV衣装「([^」]+)」(?!プレゼント)", text)
    for costume in mv_costume_matches:
        items.append(f"MV衣装「{costume}」")
    
    # 提取SPP道具
    spp_matches = re.findall(r"SPP「([^」]+)」", text)
    for spp in spp_matches:
        items.append(f"SPP「{spp}」")
    
    # 提取技能道具
    skill_matches = re.findall(r"(ライブスキル「[^」]+」|サポートスキル「[^」]+」)", text)
    for skill in skill_matches:
        items.append(skill)
    
    # 提取背景道具
    bg_matches = re.findall(r"背景「([^」]+)」", text)
    for bg in bg_matches:
        items.append(f"背景「{bg}」")
    
    # 尝试基于DOM的提取作为备选方案
    heading = soup.find(lambda t: t.name in {"h2", "h3", "div", "section"} and "取得できるスキル/アイテム" in t.get_text("\n", strip=True))
    if heading and not items:
        cur = heading
        # 遍历兄弟元素以捕获列表和段落
        for i in range(20):
            cur = cur.find_next_sibling()
            if not cur:
                break
            txt = cur.get_text("\n", strip=True)
            if not txt:
                continue
            if any(k in txt for k in ["必要素材数", "IRマス詳細", "合計ステータス", "横にスクロール"]):
                break
            # 收集有意义的行
            for ln in txt.splitlines():
                ln = ln.strip()
                if not ln:
                    continue
                if re.search(r"(スキル|ピース|アイテム|MV|ルーム衣装|SPP|背景|ボイス)", ln):
                    items.append(ln)
    
    # 备选方案：标题间的文本块
    if not items:
        m = re.search(r"取得できるスキル/アイテム\n([\s\S]+?)(?:必要素材数|IRマス詳細|合計ステータス|横にスクロール|$)", text)
        if m:
            content = m.group(1)
            lines = [ln.strip() for ln in content.splitlines() if ln.strip()]
            for ln in lines:
                if re.search(r"(スキル|ピース|アイテム|MV|ルーム衣装|SPP|背景|ボイス)", ln):
                    items.append(ln)
    
    # 最后手段：鲁棒的逐行扫描，更好地处理SPP
    if not items:
        lines = text.splitlines()
        for i, ln in enumerate(lines):
            ln = ln.strip()
            if re.match(r"^(ライブスキル「.+」|サポートスキル「.+」|MV衣装.+|ルーム衣装.+|SPP.+)$", ln):
                # 对可能分割的SPP行进行特殊处理
                if ln.startswith("SPP「") and not ln.endswith("」"):
                    # 在接下来的几行中查找结束引号
                    full_spp = ln
                    for j in range(i + 1, min(i + 3, len(lines))):
                        next_line = lines[j].strip()
                        full_spp += next_line
                        if "」" in next_line:
                            break
                    items.append(full_spp)
                else:
                    items.append(ln)
    
    # 去重同时保持顺序
    seen = set()
    unique_items = []
    for item in items:
        if item not in seen:
            seen.add(item)
            unique_items.append(item)
    
    return "；".join(unique_items)


def build_row(card_name: str, basic: Dict[str, str], status: Dict[str, Dict[str, str]], skills: Dict[str, Dict[str, str]], road_items: str) -> Dict[str, str]:
    """
    汇总并构建原始解析行（日文键），供后续模板映射使用。
    
    作用：
    - 将页面解析得到的基础信息 `basic`、属性数值 `status`、技能信息 `skills` 以及棋盘产出 `road_items`
      统一汇总为一行标准字典，键采用与页面一致的日文字段，后续由 `map_to_template` 进行中日字段映射。
    
    参数：
    - card_name: 卡面中文名或页面标题解析到的卡面名。
    - basic: 基础信息字典（如「レアリティ」「タイプ/属性」「ファン上限」「追加日」）。
    - status: 属性数值字典，包含「初期値」「無凸MAX値」「完凸MAX値」三段下的各项（Da/Vo/Pf/総合値）。
    - skills: 技能信息字典，包含「センタースキル」「ライブスキル」「サポートスキル」的名称与效果。
    - road_items: 棋盘可获得的道具/衣装/SPP/背景聚合字符串（通常为 `extract_road_items` 的输出）。
    
    返回：
    - Dict[str, str]: 以日文键为主的标准行数据，用于后续模板列映射。
    
    设计说明：
    - 字段缺失时统一回退为空字符串，避免后续写表阶段出现 NaN/None。
    - 数值优先保持原始结构，不在此阶段做“一卡/满破”选择，交由模板映射阶段处理。
    """
    
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
    """
    将解析行（日文键）映射到模板列（中文键）。
    
    功能说明：
    - 将日文字段键转换为中文模板列名
    - 根据卡面稀有度智能选择显示的数值和技能
    - 处理特殊卡面的衣装和道具逻辑
    - 解析技能等级效果和道具分类
    
    映射策略：
    1. 稀有度识别：根据レアリティ字段和卡面名称判断星级
    2. 数值选择：3-4星卡不显示数值，5星卡根据参数选择一卡/满破数值
    3. 技能处理：3星卡隐藏技能，解析Live技能Lv5和Support技能Lv3
    4. 道具分类：将道具字符串分解为MV衣装、房间衣装、背景、SPP等类别
    5. 特殊处理：针对特定卡面（如アンビバレンス HiMERU）的特殊逻辑
    
    参数：
    - row: 解析得到的行数据（日文键）
    - columns_order: 模板列顺序
    - use_initial_stats: True时使用無凸MAX値（一卡），False时优先使用完凸MAX値（満破）
    
    返回：
    - Dict[str, str]: 映射后的行数据（中文键），按模板列顺序
    
    数值选择逻辑：
    - 3-4星卡：不显示任何数值
    - 5星卡一卡模式：仅使用無凸MAX値
    - 5星卡满破模式：优先完凸MAX値，回退到無凸MAX値，最后回退到初期値
    """
    # 确定卡面稀有度
    rarity = row.get("レアリティ", "").strip()
    card_name = row.get("卡面名称", "")
    is_5_star = rarity == "☆5" or "☆5" in card_name or "★5" in card_name
    is_4_star = rarity == "☆4" or "☆4" in card_name or "★4" in card_name
    is_3_star = rarity == "☆3" or "☆3" in card_name or "★3" in card_name
    
    def pick_stat(key: str) -> str:
        """根据稀有度和模式选择合适的数值"""
        # 3星和4星卡不显示数值
        if is_3_star or is_4_star:
            return ""
            
        if use_initial_stats:
            # 一卡模式：仅使用無凸MAX値，不回退到初期値
            return (
                row.get(f"無凸MAX値 {key}")
                or ""
            )
        else:
            # 满破模式：优先完凸MAX値，然后無凸MAX値，最后初期値
            return (
                row.get(f"完凸MAX値 {key}")
                or row.get(f"無凸MAX値 {key}")
                or row.get(f"初期値 {key}")
                or ""
            )

    # 从组合效果中解析Live技能Lv5
    live_eff = row.get("ライブスキル 効果", "") or ""
    m_lv5 = re.search(r"Lv\.5：([^/\n]+)", live_eff)
    live_lv5 = m_lv5.group(1).strip() if m_lv5 else ""

    # 从组合效果中解析Support技能Lv3
    sup_eff = row.get("サポートスキル 効果", "") or ""
    m_lv3 = re.search(r"Lv\.3：([^/\n]+)", sup_eff)
    sup_lv3 = m_lv3.group(1).strip() if m_lv3 else ""

    # 分割道具项目
    mv_items: List[str] = []
    room_items: List[str] = []
    bg_items: List[str] = []
    spp_tracks: List[str] = []
    road_items = row.get("取得できるスキル/アイテム", "") or ""
    
    # 尝试不同的分隔符
    separators = ["；", "/", " / "]
    items = []
    for sep in separators:
        if sep in road_items:
            items = road_items.split(sep)
            break
    else:
        items = [road_items] if road_items else []
    
    # 检查是否为アンビバレンス HiMERU特殊卡面
    card_name = row.get("卡面名称", "")
    is_ambivalence_himeru = "裏表アンビバレンス" in card_name and "HiMERU" in card_name
    
    # 遍历道具项目进行分类
    for it in items:
        it = it.strip()
        if not it:
            continue
        
        # 提取MV衣装名称 - 所有星级都可能有MV衣装
        if "MV衣装" in it:
            if "「" in it and "」" in it:
                # 从引号中提取衣装名称: MV衣装「アンビバレンス衣装」
                costume_match = re.search(r"MV衣装「([^」]+)」", it)
                if costume_match:
                    costume_name = costume_match.group(1)
                    # 跳过促销物品（プレゼント）
                    if "プレゼント" not in it:
                        # アンビバレンス HiMERU卡面的特殊处理
                        if is_ambivalence_himeru:
                            # 只保留基础的アンビバレンス衣装，不包括变体
                            if costume_name == "アンビバレンス衣装":
                                if costume_name not in mv_items:
                                    mv_items.append(costume_name)
                        else:
                            if costume_name not in mv_items:
                                mv_items.append(costume_name)
            elif not ("一覧" in it or "リンク" in it or "あり" in it or "付き" in it or "プレゼント" in it or "ピース" in it):
                # 只包含非通用描述或衣装碎片的项目
                if not is_ambivalence_himeru:  # 特殊情况跳过
                    mv_items.append(it)
        
        # 提取房间衣装名称
        elif "ルーム衣装" in it or "房间衣装" in it:
            if "「" in it and "」" in it:
                # 从引号中提取衣装名称
                costume_match = re.search(r"(?:ルーム衣装|房间衣装)「([^」]+)」", it)
                if costume_match:
                    costume_name = costume_match.group(1)
                    if costume_name not in room_items:
                        room_items.append(costume_name)
            elif not ("一覧" in it or "リンク" in it or "あり" in it):
                room_items.append(it)
        
        # 提取背景名称
        elif "背景" in it:
            if "「" in it and "」" in it:
                bg_match = re.search(r"背景「([^」]+)」", it)
                if bg_match:
                    bg_name = bg_match.group(1)
                    if bg_name not in bg_items:
                        bg_items.append(bg_name)
            elif not ("一覧" in it or "リンク" in it):
                bg_items.append(it)
        
        # 提取SPP轨道名称
        elif "SPP" in it:
            if "「" in it and "」" in it:
                spp_match = re.search(r"SPP「([^」]+)」", it)
                if spp_match:
                    track_name = spp_match.group(1)
                    if track_name not in spp_tracks:
                        spp_tracks.append(track_name)
            elif not ("一覧" in it or "リンク" in it or "あり" in it) and len(it) > 3:
                spp_tracks.append(it)

    # アンビバレンス HiMERU卡面的特殊处理
    if is_ambivalence_himeru:
        # 确保MV和房间衣装都是アンビバレンス衣装
        if "アンビバレンス衣装" not in mv_items:
            mv_items = ["アンビバレンス衣装"]
        else:
            mv_items = ["アンビバレンス衣装"]  # 只保留基础衣装
        
        if "アンビバレンス衣装" not in room_items:
            room_items = ["アンビバレンス衣装"]

    # 卡面名称加星级后缀
    name = row.get("卡面名称", "")
    rarity = (row.get("レアリティ", "") or "").strip()
    if rarity and not rarity.startswith("☆"):
        # 标准化格式，例如 '5' -> '☆5'
        if re.match(r"^\d+$", rarity):
            rarity = f"☆{rarity}"
    if name and rarity:
        name = f"{name} {rarity}"

    # 为5星卡设置状态指示器
    status_indicator = ""
    if use_initial_stats:
        status_indicator = "一卡"
    else:
        # 检查是否为可能有双行的5星卡
        if is_5_star:
            status_indicator = "满破"

    # 对于3星卡，隐藏center技能、live技能(lv5)、support技能(lv3)
    center_skill = "" if is_3_star else row.get("センタースキル 効果", "")
    live_skill_lv5 = "" if is_3_star else live_lv5
    support_skill_lv3 = "" if is_3_star else sup_lv3

    # 优化MV衣装选择：优先选择主衣装而非变体
    if mv_items:
        # 寻找主衣装（不含括号或特殊标记）
        main_costumes = []
        for costume in mv_items:
            # 优先选择不含括号的衣装（主版本）
            if "（" not in costume and ")" not in costume:
                main_costumes.append(costume)
        
        # 如果找到主衣装，只使用第一个
        if main_costumes:
            mv_items = [main_costumes[0]]
    
    # 如果没有找到房间衣装但存在MV衣装，使用MV衣装作为房间衣装
    final_room_items = room_items if room_items else mv_items
    
    # 构建最终的映射字典
    mapped = {
        "卡面名称": name,
        "活动名称": row.get("活动名称", "") or row.get("イベント名", ""),
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
    # 保持顺序：只包含已知列；缺失的列设为空
    return {col: mapped.get(col, "") for col in columns_order}


def write_excel_rows(out_path: str, rows: List[Dict[str, str]], columns_order: List[str]) -> None:
    """
    将解析得到的行数据按模板列顺序规范化并写入 Excel 文件。
    
    参数：
    - out_path: 输出的 Excel 文件路径。
    - rows: 业务行数据列表，键为模板列（中文）或内部字段（如「イベント名」）。
    - columns_order: 模板列顺序列表，最终写出严格遵循该列顺序。
    
    行为说明：
    - 先将每一行规范为完整列集（缺失列补空字符串），避免列缺失导致写表异常。
    - 构造 DataFrame 后，若存在活动名称/卡面名称列，则进行多列排序，提升可读性与检索效率。
    - 对排序列的空值进行统一替换（空字符串/NaN -> "未知"），确保排序稳定性。
    
    注意：
    - 排序优先级为：活动名称（中文/日文） -> 卡面名称（中文/日文）。
    - 输出不包含索引列，适用于直接交付与前端展示。
    """
    normalized = [{col: r.get(col, "") for col in columns_order} for r in rows]
    df = pd.DataFrame(normalized, columns=columns_order)
    
    # 按活动名称和卡面名称排序
    sort_columns = []
    if "活动名称" in df.columns:
        sort_columns.append("活动名称")
    if "イベント名" in df.columns:
        sort_columns.append("イベント名")
    if "卡面名称" in df.columns:
        sort_columns.append("卡面名称")
    elif "カード名" in df.columns:
        sort_columns.append("カード名")
    
    # 如果找到了排序列，则进行排序
    if sort_columns:
        # 处理空值，将空字符串和NaN替换为"未知"以便排序
        for col in sort_columns:
            if col in df.columns:
                df[col] = df[col].fillna("未知").replace("", "未知")
        
        # 执行排序：先按活动名称，再按卡面名称
        df = df.sort_values(by=sort_columns, ascending=True, na_position='last')
        
        # 重置索引
        df = df.reset_index(drop=True)
    
    df.to_excel(out_path, index=False)


# 已移除：main 函数（CLI 模式与交互逻辑不在 web 链路中）


# 已移除：extract_cards_with_multithreaded_details（不在 app.py 的调用链中使用）


# 已移除：crawl_and_extract_with_multithreading（不在 app.py 的调用链中使用）


def export_cards_to_excel(url: str, output_dir: str = None, max_workers: int = 8, selected_card_urls: List[str] = None, card_url_to_event_name: Dict[str, str] = None, progress_callback=None) -> str:
    """
    导出卡面到Excel文件的主函数，供app.py调用
    
    Args:
        url: 目录页面或活动页面URL（仅用于日志记录，不再用于自动提取）
        output_dir: 输出目录，默认为项目根目录
        max_workers: 最大工作线程数
        selected_card_urls: 选中的卡面URL列表，必须提供
        card_url_to_event_name: 卡面URL到活动名称的映射字典
        progress_callback: 进度回调函数，接收(stage, progress, message, eta)参数
        
    Returns:
        str: 生成的Excel文件路径
        
    Raises:
        Exception: 当 selected_card_urls 为空或None时抛出异常
    """
    try:
        import time
        start_time = time.time()
        
        def report_progress(stage, progress, message, eta=None):
            """内部进度报告函数"""
            if progress_callback:
                progress_callback(stage, progress, message, eta)
            print(f"[{stage}] {progress:.1f}% - {message}" + (f" (预计剩余: {eta:.1f}秒)" if eta else ""))
        
        # 设置输出目录
        if output_dir is None:
            output_dir = os.path.dirname(os.path.dirname(__file__))
        
        report_progress("初始化", 5, "开始处理前端传入的卡面链接...")
        
        # 验证必须的参数
        if not selected_card_urls:
            error_msg = "错误：未提供选中的卡面URL列表 (selected_card_urls)，无法处理"
            print(f"ERROR: {error_msg}")
            report_progress("错误", 0, error_msg)
            raise Exception(error_msg)
        
        if len(selected_card_urls) == 0:
            error_msg = "错误：选中的卡面URL列表为空，无法处理"
            print(f"ERROR: {error_msg}")
            report_progress("错误", 0, error_msg)
            raise Exception(error_msg)
        
        print(f"接收到前端选中的卡面URL，共 {len(selected_card_urls)} 个")
        report_progress("验证", 10, f"验证通过，共 {len(selected_card_urls)} 个选中的卡面URL")
        
        # 构建卡面链接列表，包含活动名称信息
        links = []
        for card_url in selected_card_urls:
            if card_url_to_event_name and card_url in card_url_to_event_name:
                event_name = card_url_to_event_name[card_url]
            else:
                event_name = "未知活动"
            links.append((card_url, event_name))
            print(f"  - {card_url} (活动: {event_name})")
        
        report_progress("链接处理", 20, f"构建卡面链接列表完成，共 {len(links)} 个")
        
        # 使用多线程模式处理所有卡面
        report_progress("数据获取", 30, f"使用多线程模式处理 {len(links)} 个卡面的完整详情...")
        
        # 创建多线程获取器
        fetcher = MultiThreadedCardFetcher(
            max_workers=max_workers,
            timeout=30,
            delay=0.1
        )
        
        # 批量获取卡面完整详情
        card_details_list = fetcher.fetch_card_full_details_batch(links, progress_callback)
        
        if not card_details_list:
            error_msg = "错误：未能获取到任何卡面详情数据"
            print(f"ERROR: {error_msg}")
            report_progress("错误", 0, error_msg)
            raise Exception(error_msg)
        
        report_progress("数据获取", 80, f"多线程处理完成，成功提取 {len(card_details_list)} 个卡面的完整详情")
        
        # 使用多线程获取的数据
        rows = card_details_list
        
        report_progress("Excel生成", 85, f"开始生成Excel文件，共 {len(rows)} 个卡面数据")
        
        # 加载模板列顺序
        base_dir = os.path.dirname(os.path.dirname(__file__))
        template_path = os.path.join(base_dir, "es2 卡面名称及技能一览（新表）示例.xlsx")
        try:
            tmpl_df = pd.read_excel(template_path)
            columns_order = tmpl_df.columns.tolist()
            # 确保活动名称列被包含
            if "活动名称" not in columns_order:
                if "卡面名称" in columns_order:
                    idx = columns_order.index("卡面名称") + 1
                    columns_order.insert(idx, "活动名称")
                else:
                    columns_order.insert(1, "活动名称")
            report_progress("Excel生成", 87, f"使用模板列顺序（已添加活动名称列）")
        except Exception as e:
            report_progress("Excel生成", 87, f"无法加载模板文件，使用默认列顺序: {e}")
            # 使用默认列顺序
            columns_order = [
                "卡面名称", "活动名称", "center技能名称", "live技能名", "support技能名", "Unnamed",
                "DA", "VO", "PF", "综合值", "center技能", "live技能（lv5）", "support技能（lv3）",
                "MV衣装", "房间衣装", "背景", "spp对应乐曲", "故事"
            ]
        
        # 生成带时间戳的输出文件名
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_name = f"es2 卡面名称及技能一览{ts}.xlsx"
        out_path = os.path.join(output_dir, out_name)
        
        report_progress("Excel生成", 90, "正在处理卡面数据格式...")
        
        # 将行映射到模板格式，特别处理5星卡
        final_rows: List[Dict[str, str]] = []
        if rows and columns_order:
            for i, r in enumerate(rows):
                # 检查是否为5星卡
                rarity = r.get("レアリティ", "").strip()
                card_name = r.get("卡面名称", "")
                is_5_star = rarity == "☆5" or "☆5" in card_name or "★5" in card_name
                
                if is_5_star:
                    # 为5星卡创建两行：初始状态和满破状态
                    # 第1行：初始状态（一卡）
                    initial_row = map_to_template(r, columns_order, use_initial_stats=True)
                    final_rows.append(initial_row)
                    
                    # 第2行：满破状态（満破）
                    max_row = map_to_template(r, columns_order, use_initial_stats=False)
                    final_rows.append(max_row)
                else:
                    # 非5星卡单行
                    final_rows.append(map_to_template(r, columns_order))
        else:
            final_rows = rows
        
        report_progress("Excel生成", 95, f"正在写入Excel文件，共 {len(final_rows)} 行数据...")
        
        # 写入Excel文件
        write_excel_rows(out_path, final_rows, columns_order)
        
        # 计算总耗时
        total_time = time.time() - start_time
        report_progress("完成", 100, f"Excel文件生成完成: {out_path}", 0)
        print(f"导出完成，总耗时: {total_time:.2f}秒")
        
        return out_path
        
    except Exception as e:
        if progress_callback:
            progress_callback("错误", 0, f"导出失败: {e}")
        print(f"导出失败: {e}")
        raise


if __name__ == "__main__":
    main()
