# 开发指南

## 🚀 快速开始

### 环境要求
- **Python**: 3.11 或更高版本
- **Redis**: 6.0 或更高版本
- **操作系统**: Windows 10/11, macOS, Linux

### 安装步骤

1. **克隆项目**
```bash
git clone <repository-url>
cd es
```

2. **创建虚拟环境**
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate
```

3. **安装依赖**
```bash
pip install -r requirements.txt
```

4. **启动Redis服务**
```bash
# Windows (使用Redis for Windows)
redis-server

# macOS (使用Homebrew)
brew services start redis

# Linux (使用systemd)
sudo systemctl start redis
```

5. **启动应用**
```bash
python app.py
```

6. **访问应用**
打开浏览器访问: http://localhost:8001

---

## 🏗️ 项目架构

### 技术栈
- **后端**: Flask + Redis
- **前端**: 原生JavaScript + CSS3
- **数据处理**: Pandas + BeautifulSoup4
- **文件操作**: OpenPyXL

### 架构模式
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   前端 (JS)     │    │   后端 (Flask)  │    │   Redis 缓存    │
│                 │    │                 │    │                 │
│ • 用户交互      │◄──►│ • API 接口      │◄──►│ • 会话数据      │
│ • 数据展示      │    │ • 业务逻辑      │    │ • 临时存储      │
│ • 状态管理      │    │ • 数据处理      │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │   爬虫模块      │
                       │                 │
                       │ • 多线程爬取    │
                       │ • 数据解析      │
                       │ • Excel 导出    │
                       └─────────────────┘
```

---

## 📝 编码规范

### Python 代码规范

#### 1. 代码风格
遵循 PEP 8 标准:
```python
# 好的示例
def analyze_directory_url(url: str) -> Dict[str, Any]:
    """分析目录页URL并提取活动信息.
    
    Args:
        url: 目录页URL
        
    Returns:
        包含活动信息的字典
        
    Raises:
        ValueError: 当URL格式无效时
    """
    if not url or not isinstance(url, str):
        raise ValueError("URL必须是非空字符串")
    
    # 处理逻辑...
    return result
```

#### 2. 类型注解
使用类型注解提高代码可读性:
```python
from typing import List, Dict, Optional, Union

class RedisCache:
    def __init__(self, host: str = 'localhost', port: int = 6379) -> None:
        self.host = host
        self.port = port
        self.client: Optional[redis.Redis] = None
    
    def save_events(self, session_id: str, events: List[Dict[str, Any]]) -> bool:
        """保存活动数据到Redis"""
        try:
            # 实现逻辑...
            return True
        except Exception as e:
            logger.error(f"保存数据失败: {e}")
            return False
```

#### 3. 异常处理
```python
# 好的异常处理
try:
    result = risky_operation()
except SpecificException as e:
    logger.error(f"特定错误: {e}")
    return {"success": False, "message": "操作失败"}
except Exception as e:
    logger.error(f"未知错误: {e}")
    return {"success": False, "message": "系统错误"}
```

#### 4. 日志记录
```python
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 使用日志
logger.info("开始处理请求")
logger.warning("检测到潜在问题")
logger.error("处理失败", exc_info=True)
```

### JavaScript 代码规范

#### 1. ES6+ 语法
```javascript
// 使用 const/let 而不是 var
const API_BASE_URL = '/api';
let currentTask = null;

// 使用箭头函数
const handleResponse = (response) => {
    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }
    return response.json();
};

// 使用模板字符串
const message = `处理了 ${count} 个活动`;
```

#### 2. 异步处理
```javascript
// 使用 async/await
class ApiService {
    async getEventsFromCache(sessionId) {
        try {
            const response = await fetch(`/api/events/${sessionId}`);
            const data = await response.json();
            
            if (!data.success) {
                throw new Error(data.message);
            }
            
            return data;
        } catch (error) {
            console.error('获取数据失败:', error);
            throw error;
        }
    }
}
```

#### 3. 错误处理
```javascript
// 统一的错误处理
const handleError = (error, context = '') => {
    console.error(`${context}错误:`, error);
    
    // 显示用户友好的错误消息
    const message = error.message || '发生未知错误';
    showErrorMessage(message);
};

// 使用示例
try {
    await this.api.startCrawl(selectedEvents);
} catch (error) {
    handleError(error, '启动爬取');
}
```

---

## 🔧 开发工具配置

### VS Code 配置
创建 `.vscode/settings.json`:
```json
{
    "python.defaultInterpreterPath": "./venv/bin/python",
    "python.linting.enabled": true,
    "python.linting.pylintEnabled": true,
    "python.formatting.provider": "black",
    "editor.formatOnSave": true,
    "files.exclude": {
        "**/__pycache__": true,
        "**/*.pyc": true
    }
}
```

### Git 配置
创建 `.gitignore`:
```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
env/

# 项目特定
downloads/*.xlsx
!downloads/.gitkeep
logs/*.log
!logs/.gitkeep

# IDE
.vscode/
.idea/

# 系统文件
.DS_Store
Thumbs.db
```

---

## 🧪 测试指南

### 单元测试
创建 `tests/test_redis_utils.py`:
```python
import unittest
from unittest.mock import Mock, patch
from redis_utils import RedisCache

class TestRedisCache(unittest.TestCase):
    def setUp(self):
        self.cache = RedisCache()
    
    @patch('redis.Redis')
    def test_save_events_success(self, mock_redis):
        # 模拟Redis客户端
        mock_client = Mock()
        mock_redis.return_value = mock_client
        mock_client.setex.return_value = True
        
        # 测试数据
        session_id = "test_session"
        events = [{"name": "test_event"}]
        
        # 执行测试
        result = self.cache.save_events(session_id, events)
        
        # 验证结果
        self.assertTrue(result)
        mock_client.setex.assert_called_once()

if __name__ == '__main__':
    unittest.main()
```

### 集成测试
创建 `tests/test_api.py`:
```python
import unittest
import json
from app import app

class TestAPI(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True
    
    def test_analyze_endpoint(self):
        # 测试数据
        data = {
            "url": "https://gamerch.com/ensemble-star-music/895943"
        }
        
        # 发送请求
        response = self.app.post(
            '/api/analyze',
            data=json.dumps(data),
            content_type='application/json'
        )
        
        # 验证响应
        self.assertEqual(response.status_code, 200)
        result = json.loads(response.data)
        self.assertTrue(result['success'])
        self.assertIn('session_id', result)
```

### 运行测试
```bash
# 运行所有测试
python -m pytest tests/

# 运行特定测试文件
python -m pytest tests/test_redis_utils.py

# 生成覆盖率报告
python -m pytest --cov=. tests/
```

---

## 🐛 调试指南

### 日志调试
```python
# 在 app.py 中启用详细日志
import logging
logging.basicConfig(level=logging.DEBUG)

# 在关键位置添加日志
logger.debug(f"接收到请求: {request.json}")
logger.info(f"开始分析URL: {url}")
logger.warning(f"Redis连接失败，使用备用方案")
logger.error(f"处理失败: {str(e)}", exc_info=True)
```

### 前端调试
```javascript
// 在浏览器控制台中调试
console.log('API响应:', response);
console.warn('检测到问题:', issue);
console.error('错误详情:', error);

// 使用断点调试
debugger; // 浏览器会在此处暂停

// 检查网络请求
// 打开开发者工具 -> Network 标签页
```

### Redis 调试
```bash
# 连接到Redis CLI
redis-cli

# 查看所有键
KEYS *

# 查看特定键的值
GET es_session:20241026_abc123

# 查看键的过期时间
TTL es_session:20241026_abc123

# 删除测试数据
DEL es_session:20241026_abc123
```

---

## 📦 部署指南

### 开发环境部署
```bash
# 启动开发服务器
python app.py
```

### 生产环境部署

#### 1. 使用 Gunicorn
```bash
# 安装 Gunicorn
pip install gunicorn

# 启动应用
gunicorn -w 4 -b 0.0.0.0:8001 app:app
```

#### 2. 使用 Docker
创建 `Dockerfile`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8001

CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8001", "app:app"]
```

创建 `docker-compose.yml`:
```yaml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "8001:8001"
    depends_on:
      - redis
    environment:
      - REDIS_HOST=redis
  
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
```

#### 3. 使用 Nginx 反向代理
创建 `/etc/nginx/sites-available/es-app`:
```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
    
    location /static/ {
        alias /path/to/your/app/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

---

## 🔄 持续集成

### GitHub Actions 配置
创建 `.github/workflows/ci.yml`:
```yaml
name: CI

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      redis:
        image: redis:7
        ports:
          - 6379:6379
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install pytest pytest-cov
    
    - name: Run tests
      run: |
        pytest --cov=. tests/
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
```

---

## 📚 扩展开发

### 添加新的API端点
1. 在 `app.py` 中定义路由:
```python
@app.route('/api/new-endpoint', methods=['POST'])
def new_endpoint():
    try:
        data = request.get_json()
        # 处理逻辑
        return jsonify({"success": True, "result": result})
    except Exception as e:
        logger.error(f"新端点错误: {e}")
        return jsonify({"success": False, "message": str(e)}), 500
```

2. 在前端添加对应的API调用:
```javascript
class ApiService {
    async callNewEndpoint(data) {
        try {
            const response = await fetch('/api/new-endpoint', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(data)
            });
            return await response.json();
        } catch (error) {
            console.error('调用新端点失败:', error);
            throw error;
        }
    }
}
```

### 添加新的数据模型
使用 dataclasses 创建数据模型:
```python
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class CardInfo:
    url: str
    name: str
    rarity: str
    character: str
    skill_name: Optional[str] = None
    skill_description: Optional[str] = None

@dataclass
class EventInfo:
    name: str
    description: str
    cards: List[CardInfo]
    start_date: Optional[str] = None
    end_date: Optional[str] = None
```

---

## 🛠️ 故障排除

### 常见问题

#### 1. Redis 连接失败
```bash
# 检查 Redis 是否运行
redis-cli ping

# 检查端口是否被占用
netstat -an | grep 6379

# 重启 Redis 服务
sudo systemctl restart redis
```

#### 2. Python 依赖问题
```bash
# 重新安装依赖
pip install --force-reinstall -r requirements.txt

# 清理缓存
pip cache purge
```

#### 3. 前端资源加载失败
- 检查静态文件路径
- 确认 Flask 静态文件配置
- 检查浏览器控制台错误

#### 4. 爬取失败
- 检查目标网站是否可访问
- 验证URL格式是否正确
- 检查网络连接和代理设置

---

*本文档最后更新: 2024年10月*