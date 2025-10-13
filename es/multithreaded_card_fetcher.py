#!/usr/bin/env python3
"""
多线程卡面详情获取模块
提供高效的并发卡面信息获取功能
"""

import requests
from bs4 import BeautifulSoup
import concurrent.futures
import time
from typing import List, Tuple, Dict, Optional
import threading
from queue import Queue
import re

class MultiThreadedCardFetcher:
    """多线程卡面详情获取器"""
    
    def __init__(self, max_workers: int = 10, timeout: int = 10, delay: float = 0.1):
        """
        初始化多线程获取器
        
        Args:
            max_workers: 最大工作线程数
            timeout: 请求超时时间（秒）
            delay: 请求间隔（秒），避免过于频繁的请求
        """
        self.max_workers = max_workers
        self.timeout = timeout
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        # 统计信息
        self.stats = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'start_time': None,
            'end_time': None
        }
        
        # 线程锁
        self.lock = threading.Lock()
    
    def get_card_name_from_url(self, card_url: str) -> Tuple[str, str, str]:
        """
        从卡面URL获取卡面名称
        
        Args:
            card_url: 卡面详情页URL
            
        Returns:
            Tuple[card_url, card_name, status] - URL, 卡面名称, 状态
        """
        try:
            # 添加延迟避免过于频繁的请求
            if self.delay > 0:
                time.sleep(self.delay)
            
            response = self.session.get(card_url, timeout=self.timeout)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            # 方法1: 查找og:title meta标签
            og_title = soup.find('meta', property='og:title')
            if og_title and og_title.get('content'):
                title = og_title['content'].strip()
                card_name = self._extract_card_name_from_title(title)
                if card_name:
                    with self.lock:
                        self.stats['success'] += 1
                    return card_url, card_name, 'success'
            
            # 方法2: 查找页面title
            title_tag = soup.find('title')
            if title_tag:
                title = title_tag.get_text(strip=True)
                card_name = self._extract_card_name_from_title(title)
                if card_name:
                    with self.lock:
                        self.stats['success'] += 1
                    return card_url, card_name, 'success'
            
            # 方法3: 查找h1标签
            h1 = soup.find('h1')
            if h1:
                card_name = h1.get_text(strip=True)
                if card_name and len(card_name) > 5:
                    with self.lock:
                        self.stats['success'] += 1
                    return card_url, card_name, 'success'
            
            with self.lock:
                self.stats['failed'] += 1
            return card_url, "未找到卡面名称", 'no_name'
            
        except requests.RequestException as e:
            with self.lock:
                self.stats['failed'] += 1
            return card_url, f"请求失败: {str(e)}", 'request_error'
        except Exception as e:
            with self.lock:
                self.stats['failed'] += 1
            return card_url, f"解析失败: {str(e)}", 'parse_error'
    
    def _extract_card_name_from_title(self, title: str) -> Optional[str]:
        """从标题中提取卡面名称"""
        
        # 方法1: 查找［...］格式的卡面名
        match = re.search(r'［([^］]+)］\s*([^||\-]+)', title)
        if match:
            bracket_part = match.group(1).strip()
            name_part = match.group(2).strip()
            return f"［{bracket_part}］{name_part}"
        
        # 方法2: 查找包含［的部分
        if '［' in title and '］' in title:
            start = title.find('［')
            end = title.find('］', start) + 1
            if start != -1 and end != 0:
                card_part = title[start:end]
                # 获取］后面的部分，去掉网站名等
                remaining = title[end:].split('|')[0].split('-')[0].strip()
                return card_part + remaining
        
        return None
    
    def fetch_card_details_batch(self, card_urls: List[str]) -> Dict[str, Tuple[str, str]]:
        """
        批量获取卡面详情
        
        Args:
            card_urls: 卡面URL列表
            
        Returns:
            Dict[card_url, (card_name, status)] - URL到卡面名称和状态的映射
        """
        
        self.stats['total'] = len(card_urls)
        self.stats['success'] = 0
        self.stats['failed'] = 0
        self.stats['start_time'] = time.time()
        
        print(f"开始批量获取 {len(card_urls)} 个卡面详情...")
        print(f"使用 {self.max_workers} 个线程，请求间隔 {self.delay} 秒")
        
        results = {}
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有任务
            future_to_url = {
                executor.submit(self.get_card_name_from_url, url): url 
                for url in card_urls
            }
            
            # 收集结果
            completed = 0
            for future in concurrent.futures.as_completed(future_to_url):
                completed += 1
                try:
                    card_url, card_name, status = future.result()
                    results[card_url] = (card_name, status)
                    
                    # 每处理10个显示进度
                    if completed % 10 == 0 or completed == len(card_urls):
                        print(f"进度: {completed}/{len(card_urls)} "
                              f"({completed/len(card_urls)*100:.1f}%) "
                              f"成功: {self.stats['success']} "
                              f"失败: {self.stats['failed']}")
                        
                except Exception as e:
                    url = future_to_url[future]
                    results[url] = (f"处理异常: {str(e)}", 'exception')
                    with self.lock:
                        self.stats['failed'] += 1
        
        self.stats['end_time'] = time.time()
        self._print_stats()
        
        return results
    
    def fetch_card_full_details_batch(self, card_info_list: List[Tuple[str, str]]) -> List[Dict[str, str]]:
        """
        批量获取完整卡面详情（包括基础信息、状态、技能、道具等）
        
        Args:
            card_info_list: List[Tuple[card_url, event_name]] - 卡面URL和活动名称的列表
            
        Returns:
            List[Dict] - 完整卡面信息的列表
        """
        
        self.stats['total'] = len(card_info_list)
        self.stats['success'] = 0
        self.stats['failed'] = 0
        self.stats['start_time'] = time.time()
        
        print(f"开始批量获取 {len(card_info_list)} 个卡面的完整详情...")
        print(f"使用 {self.max_workers} 个线程，请求间隔 {self.delay} 秒")
        
        results = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有任务
            future_to_info = {
                executor.submit(self.get_card_full_details, card_url, event_name): (card_url, event_name)
                for card_url, event_name in card_info_list
            }
            
            # 收集结果
            completed = 0
            for future in concurrent.futures.as_completed(future_to_info):
                completed += 1
                try:
                    card_details = future.result()
                    if card_details:
                        results.append(card_details)
                        with self.lock:
                            self.stats['success'] += 1
                    else:
                        with self.lock:
                            self.stats['failed'] += 1
                    
                    # 每处理5个显示进度
                    if completed % 5 == 0 or completed == len(card_info_list):
                        print(f"进度: {completed}/{len(card_info_list)} "
                              f"({completed/len(card_info_list)*100:.1f}%) "
                              f"成功: {self.stats['success']} "
                              f"失败: {self.stats['failed']}")
                        
                except Exception as e:
                    card_url, event_name = future_to_info[future]
                    print(f"处理卡面失败 {card_url}: {str(e)}")
                    with self.lock:
                        self.stats['failed'] += 1
        
        self.stats['end_time'] = time.time()
        self._print_stats()
        
        return results
    
    def get_card_full_details(self, card_url: str, event_name: str) -> Optional[Dict[str, str]]:
        """
        获取单个卡面的完整详情
        
        Args:
            card_url: 卡面详情页URL
            event_name: 活动名称
            
        Returns:
            Dict - 完整的卡面信息，如果失败返回None
        """
        try:
            # 添加延迟避免过于频繁的请求
            if self.delay > 0:
                time.sleep(self.delay)
            
            response = self.session.get(card_url, timeout=self.timeout)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            # 获取卡面名称
            card_name = self._parse_card_name_from_html(response.text)
            
            # 跳过非卡面页面
            if "プロフィール" in card_name or "詳細" in card_name:
                return None
            
            # 检查是否是有效的卡面页面
            if not re.search(r"［[^］]+］", card_name):
                return None
            
            # 导入必要的函数（这里需要从crawl_es2导入）
            from crawl_es2 import extract_basic_info, extract_status, extract_skills, extract_road_items, build_row
            
            # 提取详细信息
            basic = extract_basic_info(soup)
            status = extract_status(soup)
            skills = extract_skills(soup)
            road_items = extract_road_items(soup)
            
            # 构建行数据
            row = build_row(card_name, basic, status, skills, road_items)
            row["活动名称"] = event_name
            
            return row
            
        except Exception as e:
            print(f"获取卡面详情失败 {card_url}: {str(e)}")
            return None
    
    def _parse_card_name_from_html(self, html: str) -> str:
        """从HTML中解析卡面名称"""
        soup = BeautifulSoup(html, 'lxml')
        
        # 方法1: 查找og:title meta标签
        og_title = soup.find('meta', property='og:title')
        if og_title and og_title.get('content'):
            title = og_title['content'].strip()
            card_name = self._extract_card_name_from_title(title)
            if card_name:
                return card_name
        
        # 方法2: 查找页面title
        title_tag = soup.find('title')
        if title_tag:
            title = title_tag.get_text(strip=True)
            card_name = self._extract_card_name_from_title(title)
            if card_name:
                return card_name
        
        # 方法3: 查找h1标签
        h1 = soup.find('h1')
        if h1:
            card_name = h1.get_text(strip=True)
            if card_name and len(card_name) > 5:
                return card_name
        
        return "未知卡面"
    
    def _print_stats(self):
        """打印统计信息"""
        duration = self.stats['end_time'] - self.stats['start_time']
        success_rate = (self.stats['success'] / self.stats['total'] * 100) if self.stats['total'] > 0 else 0
        
        print(f"\n=== 批量获取统计 ===")
        print(f"总数: {self.stats['total']}")
        print(f"成功: {self.stats['success']} ({success_rate:.1f}%)")
        print(f"失败: {self.stats['failed']}")
        print(f"耗时: {duration:.2f} 秒")
        print(f"平均速度: {self.stats['total']/duration:.2f} 个/秒")


def test_multithreaded_fetcher():
    """测试多线程获取器"""
    
    # 示例卡面URL列表（这里使用一些测试URL）
    test_urls = [
        "https://gamerch.com/ensemble-star-music/895943",
        "https://gamerch.com/ensemble-star-music/895944", 
        "https://gamerch.com/ensemble-star-music/895945",
    ]
    
    # 创建获取器
    fetcher = MultiThreadedCardFetcher(max_workers=5, timeout=10, delay=0.2)
    
    # 批量获取
    results = fetcher.fetch_card_details_batch(test_urls)
    
    # 显示结果
    print(f"\n=== 获取结果 ===")
    for url, (name, status) in results.items():
        card_id = url.split('/')[-1]
        print(f"卡面ID {card_id}: {name} (状态: {status})")


if __name__ == "__main__":
    test_multithreaded_fetcher()