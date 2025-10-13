# Ensemble Stars 卡面爬取与导出

一个用于从 Gamerch（あんスタMusic）页面自动提取卡面详情并导出为 Excel 的工具，支持多线程、活动名动态识别与无限制卡面数量抓取。

## 功能特性
- 多线程抓取卡面详情（名称、基础信息、数值、技能、路线项目）
- 年度活动目录页面智能提取，活动名动态识别
- 取消卡面数量上限，抓取到多少就导出多少
- 导出为 Excel（按模板列顺序），自动命名为 `es2 卡面名称及技能一览YYYYMMDD_HHMMSS.xlsx`
- 命令行可配置线程数与单线程模式

## 环境要求
- Python 3.10+（建议）
- 依赖库：`requests`, `beautifulsoup4`, `lxml`, `pandas`, `openpyxl`

安装依赖：
```powershell
pip install requests beautifulsoup4 lxml pandas openpyxl
```

## 快速开始
- 年度活动目录页（示例：2024 年活动目录）：
```powershell
cd es
python crawl_es2.py https://gamerch.com/ensemble-star-music/895943 --max-workers 8
```
- 单线程模式（便于调试）：
```powershell
python crawl_es2.py https://gamerch.com/ensemble-star-music/895943 --single-thread
```
- 验证结果文件（最新 Excel）：
```powershell
python verify_latest_crawl.py
python verify_unlimited_results.py
```

## 使用说明
- 入口脚本：`es/crawl_es2.py`
  - 自动检测目录页或详情页并提取卡面
  - 目录页使用多线程批量抓取完整详情
  - 详情页直接解析单卡面
- 多线程抓取器：`es/multithreaded_card_fetcher.py`
  - 通过 `MultiThreadedCardFetcher` 批量请求并解析
  - 可调参数：最大线程数、超时、请求间隔

## 常用命令示例
- 设置线程数为 4：
```powershell
python crawl_es2.py https://gamerch.com/ensemble-star-music/895943 --max-workers 4
```
- 运行多线程功能测试：
```powershell
python test_multithreaded_full_details.py
```
- 运行无限制提取测试：
```powershell
python test_unlimited_crawl.py
```

## 输出与模板
- 输出位置：项目根目录，文件名形如：
  - `es2 卡面名称及技能一览20251014_011423.xlsx`
- 模板文件：`es2 卡面名称及技能一览（新表）示例.xlsx`
  - 用于确定列顺序；若模板中没有“活动名称”，脚本会自动插入

## 项目结构
```
F:/Code/Trae/projects/es/
├── .gitignore
├── es2 卡面名称及技能一览（新表）示例.xlsx
├── es/
│   ├── crawl_es2.py                  # 主爬取脚本
│   ├── multithreaded_card_fetcher.py # 多线程抓取器
│   ├── verify_latest_crawl.py        # 验证最新导出文件
│   ├── verify_unlimited_results.py   # 验证无限制提取效果
│   ├── test_multithreaded_full_details.py
│   ├── test_unlimited_crawl.py
│   └── ... 其他分析/测试脚本
└── ...
```

## 说明与建议
- 若出现部分链接返回 404 属正常现象（目录中包含历史或下线页面）
- 多线程请求对站点有压力，建议合理设置 `--max-workers`（如 4~8），并保留默认请求间隔
- 若抓取进程没有日志输出，请以生成的 Excel 文件为准验证结果（可用 `verify_latest_crawl.py`）

## 版本控制与产物忽略
- `.gitignore` 已配置忽略：
  - 自动生成的 Excel 导出文件
  - 调试/测试脚本（`debug_*`, `test_*`, `verify_*`, `check_*`, `analyze_*` 等）
  - Python 缓存与虚拟环境目录
- 若需要保留特定测试脚本，请在 `.gitignore` 中添加例外规则（如 `!es/test_new_extraction.py`）

## 许可
- 本仓库代码仅用于技术研究与数据处理，不建议用于高频访问或商业用途。请遵循目标站点的使用条款。