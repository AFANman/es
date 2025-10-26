# API 接口文档

## 📋 概述

本文档描述了Ensemble Stars Music卡面爬取工具的所有API接口。所有API接口都基于RESTful设计原则，使用JSON格式进行数据交换。

## 🌐 基础信息

- **基础URL**: `http://localhost:8001/api`
- **内容类型**: `application/json`
- **字符编码**: `UTF-8`

## 📡 API 接口列表

### 1. 目录页分析接口

#### `POST /api/analyze`

分析Gamerch目录页，提取活动信息并保存到Redis缓存。

**请求参数:**
```json
{
    "url": "https://gamerch.com/ensemble-star-music/895943"
}
```

**请求示例:**
```bash
curl -X POST http://localhost:8001/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"url": "https://gamerch.com/ensemble-star-music/895943"}'
```

**成功响应 (200):**
```json
{
    "success": true,
    "session_id": "es_20241026_abc123def456",
    "event_count": 15,
    "message": "成功分析目录页，找到15个活动"
}
```

**错误响应 (400):**
```json
{
    "success": false,
    "message": "无效的URL格式"
}
```

**错误响应 (500):**
```json
{
    "success": false,
    "message": "分析目录页时发生错误: [错误详情]"
}
```

---

### 2. 活动数据获取接口

#### `GET /api/events/<session_id>`

从Redis缓存中获取指定会话的活动数据。

**路径参数:**
- `session_id`: 会话ID（由分析接口返回）

**请求示例:**
```bash
curl http://localhost:8001/api/events/es_20241026_abc123def456
```

**成功响应 (200):**
```json
{
    "success": true,
    "events": [
        {
            "name": "Starlight Festival",
            "description": "包含 12 张卡面 (2024年10月)",
            "cards": [
                {
                    "url": "https://gamerch.com/ensemble-star-music/entry/123456",
                    "month": "10",
                    "day": "15"
                }
            ],
            "card_count": 12,
            "date_info": "2024年10月"
        }
    ],
    "total_events": 15,
    "session_id": "es_20241026_abc123def456"
}
```

**错误响应 (404):**
```json
{
    "success": false,
    "message": "未找到指定会话的活动数据"
}
```

**错误响应 (500):**
```json
{
    "success": false,
    "message": "获取活动数据时发生错误: [错误详情]"
}
```

---

### 3. 爬取任务管理接口

#### `POST /api/crawl/start`

启动卡面爬取任务。

**请求参数:**
```json
{
    "events": [
        {
            "name": "Starlight Festival",
            "cards": [
                {
                    "url": "https://gamerch.com/ensemble-star-music/entry/123456",
                    "month": "10",
                    "day": "15"
                }
            ]
        }
    ]
}
```

**请求示例:**
```bash
curl -X POST http://localhost:8001/api/crawl/start \
  -H "Content-Type: application/json" \
  -d '{"events": [...]}'
```

**成功响应 (200):**
```json
{
    "success": true,
    "task_id": "crawl_20241026_xyz789",
    "message": "爬取任务已启动",
    "total_cards": 45
}
```

**错误响应 (400):**
```json
{
    "success": false,
    "message": "无效的活动数据格式"
}
```

---

#### `GET /api/progress/<task_id>`

获取爬取任务进度。

**路径参数:**
- `task_id`: 任务ID（由启动接口返回）

**请求示例:**
```bash
curl http://localhost:8001/api/progress/crawl_20241026_xyz789
```

**成功响应 (200):**
```json
{
    "success": true,
    "task_id": "crawl_20241026_xyz789",
    "status": "running",
    "progress": {
        "completed": 25,
        "total": 45,
        "percentage": 55.6
    },
    "current_activity": "正在处理: Starlight Festival",
    "estimated_time_remaining": "2分30秒",
    "logs": [
        "开始爬取活动: Starlight Festival",
        "成功获取卡面: 星之守护者 明星昴流",
        "..."
    ]
}
```

**任务完成响应 (200):**
```json
{
    "success": true,
    "task_id": "crawl_20241026_xyz789",
    "status": "completed",
    "progress": {
        "completed": 45,
        "total": 45,
        "percentage": 100
    },
    "result": {
        "file_path": "downloads/es2_卡面名称及技能一览_20241026_143022.xlsx",
        "total_cards": 45,
        "successful_cards": 43,
        "failed_cards": 2
    },
    "download_url": "/downloads/es2_卡面名称及技能一览_20241026_143022.xlsx"
}
```

**错误响应 (404):**
```json
{
    "success": false,
    "message": "未找到指定的任务"
}
```

---

#### `POST /api/cancel/<task_id>`

取消正在运行的爬取任务。

**路径参数:**
- `task_id`: 任务ID

**请求示例:**
```bash
curl -X POST http://localhost:8001/api/cancel/crawl_20241026_xyz789
```

**成功响应 (200):**
```json
{
    "success": true,
    "message": "任务已取消",
    "task_id": "crawl_20241026_xyz789"
}
```

**错误响应 (404):**
```json
{
    "success": false,
    "message": "未找到指定的任务或任务已完成"
}
```

---

## 🔧 数据模型

### Event 活动对象
```typescript
interface Event {
    name: string;              // 活动名称
    description: string;       // 活动描述
    cards: Card[];            // 卡面列表
    card_count: number;       // 卡面数量
    date_info: string;        // 日期信息
}
```

### Card 卡面对象
```typescript
interface Card {
    url: string;              // 卡面详情页URL
    month: string;            // 月份
    day: string;              // 日期
}
```

### Progress 进度对象
```typescript
interface Progress {
    completed: number;        // 已完成数量
    total: number;           // 总数量
    percentage: number;      // 完成百分比
}
```

### TaskResult 任务结果对象
```typescript
interface TaskResult {
    file_path: string;        // 输出文件路径
    total_cards: number;      // 总卡面数
    successful_cards: number; // 成功处理的卡面数
    failed_cards: number;     // 失败的卡面数
}
```

---

## 🚨 错误代码

| 状态码 | 说明 | 常见原因 |
|--------|------|----------|
| 200 | 成功 | 请求正常处理 |
| 400 | 请求错误 | 参数格式错误、缺少必需参数 |
| 404 | 资源不存在 | 会话ID或任务ID不存在 |
| 500 | 服务器错误 | 内部处理异常、Redis连接失败 |

---

## 🔄 使用流程

### 完整的爬取流程示例:

1. **分析目录页**
```bash
curl -X POST http://localhost:8001/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"url": "https://gamerch.com/ensemble-star-music/895943"}'
```

2. **获取活动数据**
```bash
curl http://localhost:8001/api/events/es_20241026_abc123def456
```

3. **启动爬取任务**
```bash
curl -X POST http://localhost:8001/api/crawl/start \
  -H "Content-Type: application/json" \
  -d '{"events": [...]}'
```

4. **监控进度**
```bash
curl http://localhost:8001/api/progress/crawl_20241026_xyz789
```

5. **下载结果**
```bash
curl -O http://localhost:8001/downloads/es2_卡面名称及技能一览_20241026_143022.xlsx
```

---

## 🛡️ 安全考虑

### 输入验证
- URL格式验证
- 参数类型检查
- 数据长度限制

### 错误处理
- 详细的错误日志记录
- 用户友好的错误消息
- 异常情况的优雅降级

### 资源保护
- 请求频率限制
- 内存使用监控
- 任务超时机制

---

## 📊 性能指标

### 响应时间
- 分析接口: < 5秒
- 数据获取: < 100ms
- 进度查询: < 50ms

### 并发能力
- 最大并发分析: 10个
- 最大并发爬取: 5个任务
- Redis连接池: 20个连接

### 缓存策略
- 活动数据缓存: 1小时
- 任务状态缓存: 24小时
- 自动清理过期数据

---

*本文档最后更新: 2024年10月*