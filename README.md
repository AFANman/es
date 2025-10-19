# Ensemble Stars 卡面爬取与导出

一个用于爬取 Gamerch「Ensemble Stars Music」卡面详情并导出为 Excel 的实用脚本集。支持多线程提取卡面完整详情、目录页智能解析、卡面数量无限制，以及结果校验与分析辅助脚本。

## 特性
- 多线程爬取：目录页与卡面详情均可并发抓取
- 不限卡面数量：移除所有数量上限，完整提取全年/页面所含卡面
- 详情完整提取：基本信息、三围、技能、路线项目等字段
- Excel 导出：按模板列顺序写入，自动包含「活动名称」列
- 校验脚本：快速验证最新导出与数量分布

## 环境要求
- Windows / PowerShell
- Python 3.11 及以上
- 依赖：`requests`、`beautifulsoup4`、`lxml`、`pandas`、`openpyxl`

安装示例（如未提供 `requirements.txt`）：
```
pip install requests beautifulsoup4 lxml pandas openpyxl
```

## 快速开始
- 年度目录页爬取（推荐多线程）：
```
python es\crawl_es2.py https://gamerch.com/ensemble-star-music/895943 --max-workers 6
```
- 单线程模式（排障用）：
```
python es\crawl_es2.py https://gamerch.com/ensemble-star-music/895943 --single-thread
```
- 验证无限制结果：
```
python es\verify_unlimited_results.py
```
- 验证最新导出：
```
python es\verify_latest_crawl.py
```

## 主要脚本
- `es/crawl_es2.py`：核心爬取与导出逻辑，支持多线程完整详情提取
- `es/multithreaded_card_fetcher.py`：并发抓取器封装
- `es/verify_unlimited_results.py`：验证最新 Excel 的卡面数量与活动分布
- `es/verify_latest_crawl.py`：查看最新导出文件的采样与列
- 其他：`find_real_events.py`、`search_correct_cards.py` 等辅助脚本

## 使用说明
- 线程控制：通过 `--max-workers N` 设置线程数（建议 4–8），未指定时默认值由脚本交互选择
- 目录页识别：自动针对年度目录页（如 `895943`）提取对应日期区域内的卡面与活动名
- 详情解析：对每个卡面详情页解析基本信息/三围/技能/路线项目等
- 数量无限制：`find_card_links` 与 `extract_cards_from_directory` 已移除上限，返回全部结果
- Excel 输出：导出文件位于项目根目录，命名为 `es2 卡面名称及技能一览YYYYMMDD_HHMMSS.xlsx`
- 模板列顺序：使用 `es2 卡面名称及技能一览（新表）示例.xlsx` 的列顺序，自动插入「活动名称」列

## 常见问题
- 页面 404 或无卡面：日志会显示未找到或跳过，继续下一个日期/链接
- 速度与稳定性：适度降低 `--max-workers`，并留出请求间隔（脚本内部已做节流）
- 输出未更新：确认脚本仍在运行，可用验证脚本查看最新 Excel 文件

## 忽略策略
项目根目录的 `.gitignore` 已配置：
- 忽略 Excel 输出（`es2 卡面名称及技能一览*.xlsx`，模板示例除外）
- 忽略调试/测试/分析脚本（`debug_*.py`、`test_*.py`、`verify_*.py`、`check_*.py`、`analyze_*.py` 等）
- 忽略 Python 缓存与虚拟环境

## 目录结构（简）
```
es/
  crawl_es2.py
  multithreaded_card_fetcher.py
  verify_unlimited_results.py
  verify_latest_crawl.py
  find_real_events.py
  search_correct_cards.py
es2 卡面名称及技能一览（新表）示例.xlsx
README.md
.gitignore
```

## 说明
- 本仓库仅用于技术研究与学习交流，请遵守目标站点的使用条款与机器人政策
- 如需定制列或导出格式，说明需求即可扩展实现