# Ensemble Stars Music 卡面爬取工具 - 项目结构文档

## 📁 项目概览

本项目是一个现代化的Web应用，用于爬取Gamerch「Ensemble Stars Music」卡面详情并导出为Excel。项目采用Flask后端 + 原生JavaScript前端的架构，支持Redis缓存和多线程爬取。

## 🏗️ 项目架构

```
es/
├── 📄 配置文件
│   ├── .gitignore                    # Git忽略规则
│   ├── requirements.txt              # Python依赖包
│   └── README.md                     # 项目说明文档
│
├── 🌐 Web应用核心
│   ├── app.py                        # Flask主应用服务器
│   ├── script.js                     # 前端主要逻辑
│   ├── styles.css                    # 全局样式文件
│   └── redis_utils.py                # Redis缓存工具类
│
├── 🎨 前端资源
│   ├── templates/                    # HTML模板目录
│   │   ├── index.html               # 主页面模板
│   │   ├── events.html              # 活动列表页模板
│   │   └── results.html             # 结果展示页模板
│   └── static/                      # 静态资源目录
│       └── events.js                # 活动列表页JavaScript
│
├── 🔧 核心爬虫模块
│   ├── es/                          # 爬虫脚本目录
│   │   ├── crawl_es2.py            # 核心爬取脚本
│   │   └── multithreaded_card_fetcher.py  # 多线程卡面获取器
│   └── extract_card_links.py       # 卡面链接提取工具
│
├── 📊 数据与输出
│   ├── downloads/                   # 下载文件存储目录
│   ├── logs/                        # 日志文件目录
│   └── es2 卡面名称及技能一览（新表）示例.xlsx  # Excel模板文件
│
├── 🛠️ 开发工具
│   ├── .trae/                       # Trae AI配置
│   │   └── rules/
│   │       └── project_rules.md     # 项目开发规则
│   ├── docs/                        # 文档目录
│   └── tools/                       # 辅助工具目录
```

## 🔍 核心文件详解

### 🌐 Web应用层

#### `app.py` - Flask主应用
- **功能**: Web服务器主入口，提供API接口
- **主要端点**:
  - `GET /` - 主页面
  - `GET /events` - 活动列表页
  - `POST /api/analyze` - 目录页分析API
  - `GET /api/events/<session_id>` - Redis活动数据获取API
  - `/api/crawl/*` - 爬取相关API接口
- **特性**: 
  - 支持CORS跨域
  - Redis缓存集成
  - 完整的错误处理和日志记录

#### `redis_utils.py` - Redis缓存工具
- **功能**: Redis连接管理和数据操作
- **核心类**: `RedisCache`
  - 连接管理和健康检查
  - 活动数据的保存、获取、删除
  - 会话ID生成和管理
- **特性**: 
  - 自动重连机制
  - 数据过期时间管理（默认1小时）
  - 完整的异常处理

#### `script.js` - 前端主逻辑
- **功能**: 主页面交互逻辑
- **核心类**: 
  - `ApiService` - API调用封装
  - `EnsembleStarsApp` - 主应用类
- **主要功能**:
  - URL验证和分析
  - 活动数据处理
  - Redis会话管理
  - 爬取进度监控

#### `static/events.js` - 活动列表页逻辑
- **功能**: 活动列表页面的所有交互
- **核心类**: `EventsPage`
- **主要功能**:
  - Redis数据获取和显示
  - 活动搜索和筛选
  - 多选和批量操作
  - 爬取任务管理

### 🎨 前端模板

#### `templates/index.html` - 主页面
- **功能**: 应用入口页面
- **特性**: 
  - 响应式设计
  - URL输入和验证
  - 现代化UI组件

#### `templates/events.html` - 活动列表页
- **功能**: 活动选择和管理界面
- **特性**:
  - 活动列表展示
  - 搜索和筛选功能
  - 爬取进度显示

#### `templates/results.html` - 结果页面
- **功能**: 爬取结果展示和下载
- **特性**:
  - 结果统计显示
  - 文件下载链接
  - 操作历史记录

### 🔧 爬虫核心

#### `es/crawl_es2.py` - 核心爬取脚本
- **功能**: 主要的卡面数据爬取逻辑
- **特性**:
  - 多线程并发爬取
  - 完整的卡面详情提取
  - Excel格式化输出
  - 进度跟踪和错误处理

#### `es/multithreaded_card_fetcher.py` - 多线程获取器
- **功能**: 并发卡面数据获取的封装
- **特性**:
  - 线程池管理
  - 请求限流和重试
  - 数据完整性验证

#### `extract_card_links.py` - 链接提取工具
- **功能**: 从目录页提取卡面链接
- **特性**:
  - 智能日期识别
  - 活动名称解析
  - 链接去重和验证

## 🔄 数据流程

### 1. 目录页分析流程
```
用户输入URL → app.py/analyze → extract_card_links → Redis缓存 → 返回session_id
```

### 2. 活动数据获取流程
```
前端请求 → app.py/events/<session_id> → Redis获取 → 返回活动数据
```

### 3. 爬取执行流程
```
选择活动 → app.py/crawl/start → es/crawl_es2.py → 多线程爬取 → Excel输出
```

## 🛠️ 技术栈

### 后端技术
- **Flask**: Web框架
- **Redis**: 数据缓存
- **BeautifulSoup4**: HTML解析
- **Pandas**: 数据处理
- **OpenPyXL**: Excel操作
- **Requests**: HTTP请求

### 前端技术
- **原生JavaScript**: 核心逻辑
- **CSS3**: 样式设计
- **HTML5**: 页面结构
- **Fetch API**: 异步请求

### 开发工具
- **Python 3.11+**: 运行环境
- **Trae AI**: 开发辅助
- **Git**: 版本控制

## 📦 依赖管理

### 核心依赖 (`requirements.txt`)
```
Flask>=2.0.0
Flask-CORS>=3.0.0
redis>=4.0.0
requests>=2.25.0
beautifulsoup4>=4.9.0
pandas>=1.3.0
openpyxl>=3.0.0
lxml>=4.6.0
```

### 开发依赖
- 日志记录: Python内置`logging`
- 并发处理: Python内置`threading`
- 数据序列化: Python内置`json`

## 🔧 配置说明

### Redis配置
- **主机**: localhost
- **端口**: 6379
- **数据库**: 0
- **过期时间**: 3600秒（1小时）

### Flask配置
- **主机**: 0.0.0.0
- **端口**: 8001
- **调试模式**: 关闭
- **CORS**: 启用

### 爬虫配置
- **默认线程数**: 4-8
- **请求间隔**: 自动节流
- **重试次数**: 3次
- **超时时间**: 30秒

## 📝 开发规范

### Python代码规范
- 遵循PEP 8风格指南
- 使用类型注解
- 完整的文档字符串
- 异常处理和日志记录

### JavaScript代码规范
- ES6+语法
- 模块化设计
- 错误处理和用户反馈
- 响应式设计原则

### 文件组织规范
- 功能模块分离
- 静态资源独立
- 配置文件集中
- 文档完整性

## 🚀 部署说明

### 开发环境
1. 安装Python 3.11+
2. 安装Redis服务器
3. 安装项目依赖: `pip install -r requirements.txt`
4. 启动应用: `python app.py`

### 生产环境
1. 使用WSGI服务器（如Gunicorn）
2. 配置反向代理（如Nginx）
3. 设置Redis持久化
4. 配置日志轮转

## 📈 扩展性

### 水平扩展
- Redis集群支持
- 多实例负载均衡
- 分布式爬取任务

### 功能扩展
- 更多数据源支持
- 自定义导出格式
- 实时数据同步
- 用户权限管理

## 🔍 监控与维护

### 日志管理
- 应用日志: `logs/` 目录
- 错误追踪: 完整的异常堆栈
- 性能监控: 请求时间和资源使用

### 数据备份
- Redis数据持久化
- Excel文件自动归档
- 配置文件版本控制

---

*本文档最后更新: 2024年10月*