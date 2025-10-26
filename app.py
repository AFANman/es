#!/usr/bin/env python3
"""
Ensemble Stars Music 卡面爬取工具 - Web服务端
集成现有爬虫脚本，提供Web API接口
"""

from flask import Flask, request, jsonify, send_file, render_template
from flask_cors import CORS
import os
import sys
import threading
import time
import uuid
from datetime import datetime
import json
import traceback
from typing import Dict, List, Optional
import logging

# 导入Redis工具
from redis_utils import save_events_to_cache, get_events_from_cache

# 添加项目路径到sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 导入现有的爬虫模块
try:
    from extract_card_links import extract_card_links_from_directory, is_target_date
    # 修复导入路径
    import sys
    import os
    es_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'es')
    if es_path not in sys.path:
        sys.path.insert(0, es_path)
    
    from multithreaded_card_fetcher import MultiThreadedCardFetcher
    from crawl_es2 import extract_cards_from_directory, crawl_page, map_to_template, write_excel_rows
    import csv
except ImportError as e:
    print(f"导入模块失败: {e}")
    print("请确保所有依赖模块都已安装")

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # 允许跨域请求

# 全局任务存储
tasks: Dict[str, Dict] = {}
task_lock = threading.Lock()

class CrawlTask:
    """爬取任务类"""
    
    def __init__(self, task_id: str, events: List[dict]):
        self.task_id = task_id
        self.events = events
        self.status = 'pending'  # pending, running, completed, failed, cancelled
        self.progress = {
            'current': 0,
            'total': len(events),
            'percentage': 0,
            'current_task': '准备中...',
            'start_time': None,
            'end_time': None,
            'logs': []
        }
        self.result_file = None
        self.error_message = None
        self.thread = None
        self.cancelled = False
        
    def add_log(self, message: str, level: str = 'info'):
        """添加日志"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_entry = {
            'timestamp': timestamp,
            'message': message,
            'level': level
        }
        self.progress['logs'].append(log_entry)
        logger.info(f"Task {self.task_id}: {message}")
        
    def update_progress(self, current: int, current_task: str = ''):
        """更新进度"""
        self.progress['current'] = current
        self.progress['percentage'] = int((current / self.progress['total']) * 100) if self.progress['total'] > 0 else 0
        if current_task:
            self.progress['current_task'] = current_task
            
    def start(self):
        """启动任务"""
        self.status = 'running'
        self.progress['start_time'] = datetime.now().isoformat()
        self.thread = threading.Thread(target=self._run_crawl)
        self.thread.start()
        
    def cancel(self):
        """取消任务"""
        self.cancelled = True
        self.status = 'cancelled'
        self.add_log('任务已取消', 'warning')
        
    def _run_crawl(self):
        """执行爬取任务"""
        try:
            self.add_log('开始爬取任务', 'info')
            
            if self.cancelled:
                return
                
            # 直接生成Excel文件
            self.add_log('正在生成Excel文件...', 'info')
            self._generate_excel()
            
            if not self.cancelled:
                self.status = 'completed'
                self.progress['end_time'] = datetime.now().isoformat()
                self.add_log('爬取任务完成', 'success')
            
        except Exception as e:
            self.status = 'failed'
            self.error_message = str(e)
            self.add_log(f'任务失败: {e}', 'error')
            logger.error(f"Task {self.task_id} failed: {e}")
            logger.error(traceback.format_exc())
            
    def _generate_excel(self):
        """直接使用 crawl_es2.py 的导出功能生成Excel文件"""
        try:
            # 选择目录页URL（优先使用前端分析得到的URL，否则回退年度目录页）
            url = None
            for ev in self.events:
                if isinstance(ev, dict) and ev.get('url'):
                    url = ev['url'].strip()
                    break
            if not url:
                url = 'https://gamerch.com/ensemble-star-music/895943'
            self.add_log(f'使用目录页URL: {url}', 'info')
    
            # 提取选中活动的卡面URL和活动名称映射
            selected_card_urls = []
            selected_event_names = []
            card_url_to_event_name = {}  # 卡面URL到活动名称的映射
            
            for ev in self.events:
                if isinstance(ev, dict):
                    # 获取活动名称用于日志显示
                    event_name = ev.get('title', ev.get('name', '')).strip()
                    if event_name:
                        selected_event_names.append(event_name)
                    
                    # 获取该活动的所有卡面URL
                    cards = ev.get('cards', [])
                    if cards:
                        self.add_log(f'活动 "{event_name}" 包含 {len(cards)} 个卡面URL', 'info')
                        for i, card_url in enumerate(cards):
                            self.add_log(f'  卡面{i+1}: {card_url}', 'info')
                            selected_card_urls.append(card_url)
                            # 建立卡面URL到活动名称的映射
                            card_url_to_event_name[card_url] = event_name
                elif isinstance(ev, str):
                    event_name = ev.strip()
                    if event_name:
                        selected_event_names.append(event_name)
            
            if selected_event_names:
                self.add_log(f'选中的活动: {", ".join(selected_event_names)}', 'info')
                self.add_log(f'选中的卡面URL总数: {len(selected_card_urls)}', 'info')
            else:
                self.add_log('未指定活动，将处理所有活动', 'info')
    
            # 直接调用 crawl_es2.py 的导出函数
            from crawl_es2 import export_cards_to_excel
            
            # 设置输出目录为downloads文件夹
            output_dir = os.path.join(os.path.dirname(__file__), 'downloads')
            os.makedirs(output_dir, exist_ok=True)
            
            # 定义进度回调函数
            def progress_callback(stage, percentage, message, eta=None):
                """进度回调函数，将进度信息添加到日志"""
                if eta is not None and eta > 0:
                    eta_str = f" (预计剩余: {eta:.1f}秒)"
                else:
                    eta_str = ""
                
                log_message = f"[{stage}] {percentage}% - {message}{eta_str}"
                self.add_log(log_message, 'info')
                
                # 更新任务进度
                self.progress['percentage'] = int(percentage)
                self.progress['current_task'] = f"[{stage}] {message}"
                
                # 根据百分比估算当前完成的任务数
                if self.progress['total'] > 0:
                    estimated_current = int((percentage / 100) * self.progress['total'])
                    self.progress['current'] = min(estimated_current, self.progress['total'])
            
            # 调用导出函数，传递选中的卡面URL、活动名称映射和进度回调
            result_file = export_cards_to_excel(
                url=url,
                output_dir=output_dir,
                max_workers=8,
                selected_card_urls=selected_card_urls if selected_card_urls else None,
                card_url_to_event_name=card_url_to_event_name if card_url_to_event_name else None,
                progress_callback=progress_callback
            )
            
            if result_file and os.path.exists(result_file):
                self.result_file = result_file
                self.add_log('Excel文件生成完成', 'success')
            else:
                raise Exception('导出函数未返回有效的文件路径')
                
        except Exception as e:
            # 让 _run_crawl 捕获并处理失败状态与日志
            raise

def analyze_directory_url(url: str) -> Dict:
    """分析目录页URL，提取活动信息"""
    try:
        logger.info(f"开始分析目录页: {url}")
        
        # 调用实际的爬虫函数
        try:
            # 首先获取页面HTML内容
            import requests
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
            logger.info(f"正在获取页面内容: {url}")
            # 在部分网络环境下可能出现证书链问题，这里临时关闭验证并抑制告警
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            response = requests.get(url, headers=headers, timeout=20, verify=False)
            response.raise_for_status()
            html_content = response.text
            logger.info(f"页面内容获取成功，长度: {len(html_content)} 字符")

            # 基于目录页内容构建卡面链接到月份的映射，用于在UI显示"2025年-月份"
            # 初始化变量，确保在异常情况下也能使用
            month_by_card_url = {}
            month_day_by_card_url = {}
            
            try:
                from bs4 import BeautifulSoup
                import calendar
                from crawl_es2 import find_cards_by_date_with_dynamic_event_names

                soup = BeautifulSoup(html_content, "lxml")

                # 目标日：每月 1、10、14、15、25、月末前一天、月末
                target_days_base = [1, 10, 14, 15, 25]
                for m in range(1, 13):
                    month_end = calendar.monthrange(2025, m)[1]
                    pre_end = month_end - 1
                    day_candidates = sorted(set(target_days_base + [pre_end, month_end]))

                    for d in day_candidates:
                        # 形式一：前导零
                        pattern1 = f"{m:02d}月{d:02d}日"
                        section1 = find_cards_by_date_with_dynamic_event_names(soup, pattern1, expected_event_hint=None)
                        if section1:
                            for card_url, _ in section1:
                                if card_url not in month_by_card_url:
                                    month_by_card_url[card_url] = m
                                if card_url not in month_day_by_card_url:
                                    month_day_by_card_url[card_url] = (m, d)
                        # 形式二：不带前导零
                        pattern2 = f"{m}月{d}日"
                        section2 = find_cards_by_date_with_dynamic_event_names(soup, pattern2, expected_event_hint=None)
                        if section2:
                            for card_url, _ in section2:
                                if card_url not in month_by_card_url:
                                    month_by_card_url[card_url] = m
                                if card_url not in month_day_by_card_url:
                                    month_day_by_card_url[card_url] = (m, d)

                logger.info(f"日期映射构建完成，覆盖 {len(month_by_card_url)} 个卡面链接")
            except Exception as map_err:
                logger.warning(f"构建卡面-月份映射失败: {map_err}")
                month_by_card_url = {}

            # 调用爬虫函数
            card_event_pairs = extract_cards_from_directory(html_content, url)
            logger.info(f"从目录页提取到 {len(card_event_pairs)} 个卡面-活动对")
            
            # 添加详细的调试信息
            if card_event_pairs:
                logger.info("提取到的活动详情:")
                event_counts = {}
                for card_url, event_name in card_event_pairs:
                    event_counts[event_name] = event_counts.get(event_name, 0) + 1
                
                for event_name, count in event_counts.items():
                    logger.info(f"  - {event_name}: {count} 张卡面")
                    
            else:
                logger.warning("未提取到任何卡面-活动对")
            
            # 按活动名称分组
            events_dict = {}
            for card_url, event_name in card_event_pairs:
                if event_name not in events_dict:
                    events_dict[event_name] = {
                        'id': str(len(events_dict) + 1),
                        'title': event_name,
                        'date': '2025年',
                        'url': card_url,
                        'description': f'包含 {len([p for p in card_event_pairs if p[1] == event_name])} 张卡面',
                        'cards': []
                    }
                events_dict[event_name]['cards'].append(card_url)
            
            # 转换为列表格式
            events = list(events_dict.values())
            
            # 更新描述信息
            for event in events:
                card_count = len(event['cards'])
                event['description'] = f'包含 {card_count} 张卡面'

                # 优先根据卡面链接映射出所属“月份+日期”
                md_pairs = []
                for u in event['cards']:
                    md = month_day_by_card_url.get(u)
                    if md:
                        md_pairs.append(md)
                if md_pairs:
                    md_counts = {}
                    for md in md_pairs:
                        md_counts[md] = md_counts.get(md, 0) + 1
                    dominant_md = max(md_counts, key=md_counts.get)
                    mm, dd = dominant_md
                    event['date'] = f"2025年{mm:02d}月{dd:02d}日"
                else:
                    # 回退一：从活动名称中提取“月日”
                    import re
                    m = re.search(r'(\d{1,2})月(\d{1,2})日', event['title'])
                    if m:
                        month = int(m.group(1))
                        day = int(m.group(2))
                        event['date'] = f"2025年{month:02d}月{day:02d}日"
                    else:
                        # 回退二：仅有月份映射时，填充未知日
                        months = []
                        for u in event['cards']:
                            mm = month_by_card_url.get(u)
                            if mm:
                                months.append(mm)
                        if months:
                            counts = {}
                            for mm in months:
                                counts[mm] = counts.get(mm, 0) + 1
                            dominant_month = max(counts, key=counts.get)
                            event['date'] = f"2025年{dominant_month:02d}月??日"
                        else:
                            event['date'] = "2025年??月??日"
            logger.info(f"分析完成，找到 {len(events)} 个活动")
            
            return {
                'success': True,
                'events': events,
                'message': f'成功找到 {len(events)} 个活动，共 {len(card_event_pairs)} 张卡面'
            }
            
        except Exception as crawl_error:
            logger.warning(f"爬虫函数调用失败: {crawl_error}")
            # 爬虫失败时返回空列表，不使用备用数据
            return {
                'success': False,
                'events': [],
                'message': f'爬虫失败: {str(crawl_error)}'
            }
        
    except Exception as e:
        logger.error(f"分析目录页失败: {e}")
        return {
            'success': False,
            'events': [],
            'message': f'分析失败: {str(e)}'
        }

@app.route('/')
def index():
    """主页"""
    return render_template('index.html')

@app.route('/results')
def results():
    """结果页面"""
    task_id = request.args.get('task_id')
    if not task_id:
        return render_template('index.html')  # 如果没有task_id，返回主页
    
    with task_lock:
        task = tasks.get(task_id)
    
    if not task:
        return render_template('index.html')  # 如果任务不存在，返回主页
    
    return render_template('results.html', task_id=task_id, task=task)

@app.route('/events')
def events():
    """活动列表页面"""
    return render_template('events.html')

@app.route('/api/analyze', methods=['POST'])
def analyze():
    """分析目录页API"""
    try:
        data = request.get_json()
        url = data.get('url', '').strip()
        
        if not url:
            return jsonify({
                'success': False,
                'message': '请提供目录页URL'
            }), 400
            
        # 验证URL格式
        if 'gamerch.com' not in url or 'ensemble-star-music' not in url:
            return jsonify({
                'success': False,
                'message': '请提供有效的Gamerch Ensemble Stars Music链接'
            }), 400
            
        # 分析目录页
        result = analyze_directory_url(url)
        
        if result['success'] and result['events']:
            # 将活动数据保存到Redis
            session_id = save_events_to_cache(result['events'])
            
            if session_id:
                logger.info(f"活动数据已保存到Redis，会话ID: {session_id}")
                return jsonify({
                    'success': True,
                    'session_id': session_id,
                    'events_count': len(result['events']),
                    'message': result['message']
                })
            else:
                logger.warning("保存活动数据到Redis失败，回退到原始方式")
                # Redis保存失败时，回退到原始方式
                return jsonify(result)
        else:
            # 分析失败或无活动数据
            return jsonify(result)
        
    except Exception as e:
        logger.error(f"分析API错误: {e}")
        return jsonify({
            'success': False,
            'message': f'服务器错误: {str(e)}'
        }), 500

@app.route('/api/events/<session_id>', methods=['GET'])
def get_events(session_id):
    """从Redis获取活动数据API"""
    try:
        logger.info(f"获取活动数据请求，会话ID: {session_id}")
        
        # 从Redis获取活动数据
        events_data = get_events_from_cache(session_id)
        
        if events_data is not None:
            logger.info(f"成功从Redis获取活动数据，活动数量: {len(events_data)}")
            return jsonify({
                'success': True,
                'events': events_data,
                'message': f'成功获取 {len(events_data)} 个活动'
            })
        else:
            logger.warning(f"Redis中未找到会话ID为 {session_id} 的活动数据")
            return jsonify({
                'success': False,
                'message': '活动数据不存在或已过期，请重新分析目录页'
            }), 404
            
    except Exception as e:
        logger.error(f"获取活动数据API错误: {e}")
        return jsonify({
            'success': False,
            'message': f'服务器错误: {str(e)}'
        }), 500

@app.route('/api/crawl/start', methods=['POST'])
def start_crawl():
    """开始爬取API"""
    try:
        logger.info("收到爬取启动请求")
        data = request.get_json()
        logger.info(f"请求数据: {data}")
        
        events = data.get('events', [])
        logger.info(f"活动列表: {events}")
        
        if not events:
            logger.warning("未提供活动列表")
            return jsonify({
                'success': False,
                'message': '请选择要爬取的活动'
            }), 400
            
        # 创建新任务
        task_id = str(uuid.uuid4())
        logger.info(f"生成任务ID: {task_id}")
        
        task = CrawlTask(task_id, events)
        logger.info(f"创建任务对象: {task}")
        
        with task_lock:
            tasks[task_id] = task
            logger.info(f"任务已添加到任务列表，当前任务数: {len(tasks)}")
            
        # 启动任务
        logger.info("启动任务...")
        task.start()
        logger.info("任务启动完成")
        
        logger.info(f"创建爬取任务: {task_id}, 活动数量: {len(events)}")
        
        response_data = {
            'success': True,
            'taskId': task_id,
            'message': '爬取任务已启动'
        }
        logger.info(f"返回响应: {response_data}")
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"启动爬取API错误: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'message': f'启动失败: {str(e)}'
        }), 500

@app.route('/api/progress/<task_id>', methods=['GET'])
def get_progress(task_id):
    """获取爬取进度API"""
    try:
        with task_lock:
            task = tasks.get(task_id)
            
        if not task:
            return jsonify({
                'success': False,
                'message': '任务不存在'
            }), 404
        
        # 构建响应数据
        response_data = {
            'success': True,
            'status': task.status,
            'progress': task.progress,
            'resultFile': task.result_file,
            'errorMessage': task.error_message
        }
        
        # 如果任务完成且有结果文件，添加下载URL
        if task.status == 'completed' and task.result_file:
            response_data['download_url'] = f'/es/api/download/{task_id}'
            
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"获取进度API错误: {e}")
        return jsonify({
            'success': False,
            'message': f'获取进度失败: {str(e)}'
        }), 500

@app.route('/api/cancel/<task_id>', methods=['POST'])
def cancel_crawl(task_id):
    """取消爬取API"""
    try:
        with task_lock:
            task = tasks.get(task_id)
            
        if not task:
            return jsonify({
                'success': False,
                'message': '任务不存在'
            }), 404
            
        task.cancel()
        
        logger.info(f"取消爬取任务: {task_id}")
        
        return jsonify({
            'success': True,
            'message': '任务已取消'
        })
        
    except Exception as e:
        logger.error(f"取消爬取API错误: {e}")
        return jsonify({
            'success': False,
            'message': f'取消失败: {str(e)}'
        }), 500

@app.route('/api/download/<task_id>', methods=['GET'])
def download_result(task_id):
    """下载结果文件API"""
    try:
        with task_lock:
            task = tasks.get(task_id)
            
        if not task:
            return jsonify({
                'success': False,
                'message': '任务不存在'
            }), 404
            
        if task.status != 'completed' or not task.result_file:
            return jsonify({
                'success': False,
                'message': '文件尚未准备好'
            }), 400
            
        if not os.path.exists(task.result_file):
            return jsonify({
                'success': False,
                'message': '文件不存在'
            }), 404
            
        return send_file(
            task.result_file,
            as_attachment=True,
            download_name=os.path.basename(task.result_file)
        )
        
    except Exception as e:
        logger.error(f"下载文件API错误: {e}")
        return jsonify({
            'success': False,
            'message': f'下载失败: {str(e)}'
        }), 500

@app.route('/api/tasks', methods=['GET'])
def list_tasks():
    """获取任务列表API"""
    try:
        with task_lock:
            task_list = []
            for task_id, task in tasks.items():
                task_list.append({
                    'taskId': task_id,
                    'status': task.status,
                    'eventCount': len(task.events),
                    'progress': task.progress['percentage'],
                    'startTime': task.progress['start_time'],
                    'endTime': task.progress['end_time']
                })
                
        return jsonify({
            'success': True,
            'tasks': task_list
        })
        
    except Exception as e:
        logger.error(f"获取任务列表API错误: {e}")
        return jsonify({
            'success': False,
            'message': f'获取任务列表失败: {str(e)}'
        }), 500

# 静态文件服务
@app.route('/es/static/styles.css')
def styles():
    return send_file('static/styles.css')

@app.route('/es/static/script.js')
def script():
    return send_file('static/script.js')

@app.route('/es/static/events.js')
def events_js():
    return send_file('static/events.js')

# 清理过期任务的后台线程
def cleanup_old_tasks():
    """清理过期任务"""
    while True:
        try:
            current_time = time.time()
            with task_lock:
                expired_tasks = []
                for task_id, task in tasks.items():
                    # 清理24小时前的任务
                    if (task.status in ['completed', 'failed', 'cancelled'] and 
                        task.progress.get('end_time')):
                        end_time = datetime.fromisoformat(task.progress['end_time']).timestamp()
                        if current_time - end_time > 24 * 3600:  # 24小时
                            expired_tasks.append(task_id)
                            
                for task_id in expired_tasks:
                    task = tasks.pop(task_id)
                    # 删除结果文件
                    if task.result_file and os.path.exists(task.result_file):
                        try:
                            os.remove(task.result_file)
                        except:
                            pass
                    logger.info(f"清理过期任务: {task_id}")
                    
        except Exception as e:
            logger.error(f"清理任务错误: {e}")
            
        time.sleep(3600)  # 每小时检查一次

if __name__ == '__main__':
    # 启动清理线程
    cleanup_thread = threading.Thread(target=cleanup_old_tasks, daemon=True)
    cleanup_thread.start()
    
    # 确保下载目录存在
    os.makedirs('downloads', exist_ok=True)
    
    logger.info("启动Ensemble Stars Music卡面爬取工具服务")
    app.run(host='0.0.0.0', port=8001, debug=False)