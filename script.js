// 全局状态管理
class AppState {
    constructor() {
        this.currentPage = 'start';
        this.events = [];
        this.selectedEvents = new Set();
        this.isLoading = false;
        this.crawlProgress = {
            current: 0,
            total: 0,
            percentage: 0,
            currentTask: '',
            startTime: null,
            logs: []
        };
    }

    // 切换页面
    switchPage(pageName) {
        const pages = document.querySelectorAll('.page');
        pages.forEach(page => page.classList.remove('active'));
        
        const targetPage = document.getElementById(pageName + 'Page');
        if (targetPage) {
            targetPage.classList.add('active');
            this.currentPage = pageName;
        }
    }

    // 添加事件
    setEvents(events) {
        this.events = events;
        this.selectedEvents.clear();
        this.updateEventDisplay();
    }

    // 选择/取消选择事件
    toggleEvent(eventId) {
        if (this.selectedEvents.has(eventId)) {
            this.selectedEvents.delete(eventId);
        } else {
            this.selectedEvents.add(eventId);
        }
        this.updateEventDisplay();
    }

    // 全选事件
    selectAllEvents() {
        this.events.forEach(event => this.selectedEvents.add(event.id));
        this.updateEventDisplay();
    }

    // 清空选择
    clearAllEvents() {
        this.selectedEvents.clear();
        this.updateEventDisplay();
    }

    // 更新事件显示
    updateEventDisplay() {
        this.renderEventList();
        this.updateSelectedCount();
        this.updateActionSummary();
        this.updateCrawlButton();
    }

    // 渲染事件列表
    renderEventList() {
        const eventList = document.getElementById('eventList');
        const searchTerm = document.getElementById('eventSearch').value.toLowerCase();
        
        const filteredEvents = this.events.filter(event => 
            event.title.toLowerCase().includes(searchTerm) ||
            event.date.toLowerCase().includes(searchTerm)
        );

        eventList.innerHTML = filteredEvents.map(event => `
            <div class="event-item ${this.selectedEvents.has(event.id) ? 'selected' : ''}" 
                 data-event-id="${event.id}">
                <div class="event-checkbox ${this.selectedEvents.has(event.id) ? 'checked' : ''}"
                     data-event-id="${event.id}"></div>
                <div class="event-info">
                    <div class="event-title">${event.title}</div>
                    <div class="event-date">${event.date}</div>
                </div>
            </div>
        `).join('');

        // 更新事件计数
        document.getElementById('eventCount').textContent = `${filteredEvents.length} 个活动`;
    }

    // 更新选中计数
    updateSelectedCount() {
        const count = this.selectedEvents.size;
        document.getElementById('selectedCount').textContent = `已选择 ${count} 个活动`;
    }

    // 更新操作摘要
    updateActionSummary() {
        const count = this.selectedEvents.size;
        const summary = count > 0 ? `准备爬取 ${count} 个活动的卡面数据` : '请选择要爬取的活动';
        document.getElementById('actionSummary').textContent = summary;
    }

    // 更新爬取按钮状态
    updateCrawlButton() {
        const button = document.getElementById('startCrawlBtn');
        const hasSelection = this.selectedEvents.size > 0;
        button.disabled = !hasSelection || this.isLoading;
    }

    // 更新爬取进度
    updateProgress(current, total, currentTask = '') {
        this.crawlProgress.current = current;
        this.crawlProgress.total = total;
        this.crawlProgress.percentage = total > 0 ? Math.round((current / total) * 100) : 0;
        this.crawlProgress.currentTask = currentTask;

        // 更新UI
        document.getElementById('progressFill').style.width = `${this.crawlProgress.percentage}%`;
        document.getElementById('progressText').textContent = `${this.crawlProgress.percentage}%`;
        document.getElementById('currentTask').textContent = currentTask;
        document.getElementById('completedCount').textContent = current;
        document.getElementById('totalCount').textContent = total;

        // 计算预计剩余时间
        if (this.crawlProgress.startTime && current > 0) {
            const elapsed = Date.now() - this.crawlProgress.startTime;
            const avgTime = elapsed / current;
            const remaining = (total - current) * avgTime;
            const minutes = Math.ceil(remaining / 60000);
            document.getElementById('estimatedTime').textContent = `约 ${minutes} 分钟`;
        }
    }

    // 添加日志
    addLog(message, type = 'info') {
        const timestamp = new Date().toLocaleTimeString();
        const logEntry = { timestamp, message, type };
        this.crawlProgress.logs.push(logEntry);

        const logContainer = document.getElementById('logContainer');
        const logElement = document.createElement('div');
        logElement.className = `log-entry ${type}`;
        logElement.textContent = `[${timestamp}] ${message}`;
        
        logContainer.appendChild(logElement);
        logContainer.scrollTop = logContainer.scrollHeight;

        // 限制日志数量
        if (this.crawlProgress.logs.length > 100) {
            this.crawlProgress.logs.shift();
            logContainer.removeChild(logContainer.firstChild);
        }
    }
}

// 通知系统
class NotificationSystem {
    constructor() {
        this.container = document.getElementById('notification');
        this.timeout = null;
    }

    show(message, type = 'info', duration = 5000) {
        // 清除之前的定时器
        if (this.timeout) {
            clearTimeout(this.timeout);
        }

        // 更新通知内容
        this.container.className = `notification ${type}`;
        this.container.querySelector('.notification-message').textContent = message;
        
        // 显示通知
        this.container.classList.add('show');

        // 自动隐藏
        if (duration > 0) {
            this.timeout = setTimeout(() => {
                this.hide();
            }, duration);
        }
    }

    hide() {
        this.container.classList.remove('show');
        if (this.timeout) {
            clearTimeout(this.timeout);
            this.timeout = null;
        }
    }
}

// 加载遮罩管理
class LoadingManager {
    constructor() {
        this.overlay = document.getElementById('loadingOverlay');
        this.text = document.getElementById('loadingText');
    }

    show(message = '正在处理...') {
        this.text.textContent = message;
        this.overlay.classList.add('active');
    }

    hide() {
        this.overlay.classList.remove('active');
    }
}

// API 服务
class ApiService {
    constructor() {
        this.baseUrl = '/api'; // 假设后端API的基础URL
    }

    // 分析目录页
    async analyzeDirectory(url) {
        try {
            const response = await fetch('/api/analyze', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ url })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('分析目录页失败:', error);
            throw error;
        }
    }

    // 开始爬取
    async startCrawl(eventIds) {
        try {
            const response = await fetch(`${this.baseUrl}/crawl`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ eventIds })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('开始爬取失败:', error);
            throw error;
        }
    }

    // 获取爬取进度
    async getCrawlProgress(taskId) {
        try {
            const response = await fetch(`${this.baseUrl}/progress/${taskId}`);
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('获取进度失败:', error);
            throw error;
        }
    }

    // 取消爬取
    async cancelCrawl(taskId) {
        try {
            const response = await fetch(`${this.baseUrl}/cancel/${taskId}`, {
                method: 'POST'
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('取消爬取失败:', error);
            throw error;
        }
    }
}

// 主应用类
class EnsembleStarsApp {
    constructor() {
        this.state = new AppState();
        this.notification = new NotificationSystem();
        this.loading = new LoadingManager();
        this.api = new ApiService();
        this.currentTaskId = null;
        this.progressInterval = null;

        this.init();
    }

    init() {
        this.bindEvents();
        this.setupValidation();
        
        // 模拟数据（开发阶段使用）
        this.setupMockData();
    }

    // 绑定事件监听器
    bindEvents() {
        // 启动页事件
        document.getElementById('urlInput').addEventListener('input', this.handleUrlInput.bind(this));
        document.getElementById('analyzeBtn').addEventListener('click', this.handleAnalyze.bind(this));

        // 活动页事件
        document.getElementById('backBtn').addEventListener('click', () => {
            this.state.switchPage('start');
        });

        document.getElementById('selectAllBtn').addEventListener('click', () => {
            this.state.selectAllEvents();
        });

        document.getElementById('clearAllBtn').addEventListener('click', () => {
            this.state.clearAllEvents();
        });

        document.getElementById('eventSearch').addEventListener('input', () => {
            this.state.updateEventDisplay();
        });

        document.getElementById('startCrawlBtn').addEventListener('click', this.handleStartCrawl.bind(this));
        document.getElementById('cancelCrawlBtn').addEventListener('click', this.handleCancelCrawl.bind(this));

        // 事件列表点击事件（事件委托）
        document.getElementById('eventList').addEventListener('click', this.handleEventClick.bind(this));

        // 通知关闭事件
        document.querySelector('.notification-close').addEventListener('click', () => {
            this.notification.hide();
        });
    }

    // 设置输入验证
    setupValidation() {
        const urlInput = document.getElementById('urlInput');
        const analyzeBtn = document.getElementById('analyzeBtn');
        const feedback = document.getElementById('inputFeedback');

        // 初始状态：允许使用默认链接
        analyzeBtn.disabled = false;

        urlInput.addEventListener('input', () => {
            const url = urlInput.value.trim();
            const isValid = this.validateUrl(url);

            if (url === '') {
                feedback.textContent = '将使用默认链接进行分析';
                feedback.className = 'input-feedback';
                analyzeBtn.disabled = false; // 允许使用默认链接
            } else if (isValid) {
                feedback.textContent = '✓ 链接格式正确';
                feedback.className = 'input-feedback success';
                analyzeBtn.disabled = false;
            } else {
                feedback.textContent = '✗ 请输入有效的Gamerch链接';
                feedback.className = 'input-feedback error';
                analyzeBtn.disabled = true;
            }
        });

        // 触发初始状态
        urlInput.dispatchEvent(new Event('input'));
    }

    // 验证URL格式
    validateUrl(url) {
        if (!url) return true; // 空URL被认为是有效的（使用默认链接）
        try {
            const urlObj = new URL(url);
            return urlObj.hostname.includes('gamerch.com') && 
                   urlObj.pathname.includes('ensemble-star-music');
        } catch {
            return false;
        }
    }

    // 处理URL输入
    handleUrlInput(event) {
        // 输入验证已在setupValidation中处理
    }

    // 处理分析按钮点击
    async handleAnalyze() {
        let url = document.getElementById('urlInput').value.trim();
        const analyzeBtn = document.getElementById('analyzeBtn');

        // 如果没有输入URL，使用默认链接
        if (!url) {
            url = 'https://gamerch.com/ensemble-star-music/895943';
            document.getElementById('urlInput').value = url;
        }

        if (!this.validateUrl(url)) {
            this.notification.show('请输入有效的目录页链接', 'error');
            return;
        }

        try {
            // 显示加载状态
            analyzeBtn.classList.add('loading');
            this.loading.show('正在分析目录页，请稍候...');

            // 调用真实的API分析目录页
            const result = await this.api.analyzeDirectory(url);

            if (result.success && result.events.length > 0) {
                this.state.setEvents(result.events);
                this.state.switchPage('event');
                this.notification.show(`成功找到 ${result.events.length} 个活动`, 'success');
            } else {
                this.notification.show('未找到符合条件的活动', 'warning');
            }

        } catch (error) {
            console.error('分析失败:', error);
            this.notification.show('分析目录页失败，请检查链接或稍后重试', 'error');
        } finally {
            analyzeBtn.classList.remove('loading');
            this.loading.hide();
        }
    }

    // 分析目录页（模拟实现）
    async analyzeDirectory(url) {
        // 模拟API调用延迟
        await new Promise(resolve => setTimeout(resolve, 2000));

        // 模拟返回数据
        return {
            success: true,
            events: [
                {
                    id: '1',
                    title: '感谢祭◇バタリオン・バタフライin WILDLAND',
                    date: '2024年10月',
                    url: 'https://gamerch.com/ensemble-star-music/event1',
                    description: '10月活动 - 感谢祭系列'
                },
                {
                    id: '2',
                    title: 'Witchcraft Halloween Event',
                    date: '2024年10月',
                    url: 'https://gamerch.com/ensemble-star-music/event2',
                    description: '万圣节主题活动'
                },
                {
                    id: '3',
                    title: 'Bright me up!! Stage：宙',
                    date: '2024年10月',
                    url: 'https://gamerch.com/ensemble-star-music/event3',
                    description: 'Bright me up系列活动'
                },
                {
                    id: '4',
                    title: 'SELECTION 10 UNIT SONG 06',
                    date: '2024年10月',
                    url: 'https://gamerch.com/ensemble-star-music/event4',
                    description: '单元歌曲纪念活动'
                }
            ]
        };
    }

    // 处理事件点击
    handleEventClick(event) {
        const eventItem = event.target.closest('.event-item');
        const checkbox = event.target.closest('.event-checkbox');
        
        if (eventItem) {
            const eventId = eventItem.dataset.eventId;
            
            if (checkbox) {
                // 点击复选框，切换选择状态
                this.state.toggleEvent(eventId);
            } else {
                // 点击其他区域，显示预览
                this.showEventPreview(eventId);
            }
        }
    }

    // 显示事件预览
    showEventPreview(eventId) {
        const event = this.state.events.find(e => e.id === eventId);
        if (!event) return;

        // 移除之前的活动状态
        document.querySelectorAll('.event-item').forEach(item => {
            item.classList.remove('active');
        });

        // 添加当前活动状态
        const eventItem = document.querySelector(`[data-event-id="${eventId}"]`);
        if (eventItem) {
            eventItem.classList.add('active');
        }

        // 更新预览内容
        const previewContent = document.getElementById('previewContent');
        previewContent.innerHTML = `
            <div class="event-preview">
                <h3>${event.title}</h3>
                <p class="event-date">${event.date}</p>
                <p class="event-description">${event.description || '暂无描述'}</p>
                <div class="event-actions">
                    <button class="preview-btn" onclick="window.open('${event.url}', '_blank')">
                        <i class="fas fa-external-link-alt"></i>
                        查看原页面
                    </button>
                </div>
            </div>
        `;
    }

    // 处理开始爬取
    async handleStartCrawl() {
        if (this.state.selectedEvents.size === 0) {
            this.notification.show('请先选择要爬取的活动', 'warning');
            return;
        }

        try {
            const crawlBtn = document.getElementById('startCrawlBtn');
            crawlBtn.classList.add('loading');
            this.state.isLoading = true;

            // 显示进度区域
            const progressSection = document.getElementById('progressSection');
            progressSection.style.display = 'block';
            progressSection.scrollIntoView({ behavior: 'smooth' });

            // 初始化进度
            this.state.crawlProgress.startTime = Date.now();
            this.state.crawlProgress.logs = [];
            this.state.updateProgress(0, this.state.selectedEvents.size, '准备开始爬取...');

            // 开始爬取
            const eventIds = Array.from(this.state.selectedEvents);
            const result = await this.startCrawl(eventIds);

            if (result.success) {
                this.currentTaskId = result.taskId;
                this.startProgressMonitoring();
                this.state.addLog('爬取任务已启动', 'success');
            } else {
                throw new Error(result.message || '启动爬取失败');
            }

        } catch (error) {
            console.error('启动爬取失败:', error);
            this.notification.show('启动爬取失败，请稍后重试', 'error');
            this.state.isLoading = false;
            document.getElementById('startCrawlBtn').classList.remove('loading');
        }
    }

    // 开始爬取（模拟实现）
    async startCrawl(eventIds) {
        // 模拟API调用延迟
        await new Promise(resolve => setTimeout(resolve, 1000));

        return {
            success: true,
            taskId: 'task_' + Date.now(),
            message: '爬取任务已启动'
        };
    }

    // 开始进度监控
    startProgressMonitoring() {
        let progress = 0;
        const total = this.state.selectedEvents.size;
        
        this.progressInterval = setInterval(() => {
            progress++;
            
            if (progress <= total) {
                const currentTask = `正在处理第 ${progress} 个活动...`;
                this.state.updateProgress(progress, total, currentTask);
                this.state.addLog(`完成活动 ${progress}/${total}`, 'info');
                
                if (progress === total) {
                    this.completeCrawl();
                }
            }
        }, 2000); // 每2秒更新一次进度
    }

    // 完成爬取
    completeCrawl() {
        if (this.progressInterval) {
            clearInterval(this.progressInterval);
            this.progressInterval = null;
        }

        this.state.isLoading = false;
        this.state.addLog('所有活动处理完成', 'success');
        this.state.addLog('正在生成Excel文件...', 'info');

        // 模拟文件生成
        setTimeout(() => {
            this.state.addLog('Excel文件生成完成', 'success');
            this.downloadExcel();
            
            document.getElementById('startCrawlBtn').classList.remove('loading');
            this.notification.show('爬取完成！Excel文件已下载', 'success');
        }, 1000);
    }

    // 下载Excel文件
    downloadExcel() {
        // 创建模拟的Excel文件下载
        const filename = `es_cards_${new Date().toISOString().split('T')[0]}.xlsx`;
        
        // 这里应该是实际的文件下载逻辑
        // 现在只是模拟下载
        const link = document.createElement('a');
        link.href = '#'; // 实际应该是文件的URL
        link.download = filename;
        link.textContent = '下载Excel文件';
        
        this.state.addLog(`文件已保存: ${filename}`, 'success');
        
        // 实际项目中，这里应该触发真实的文件下载
        // link.click();
    }

    // 处理取消爬取
    async handleCancelCrawl() {
        if (!this.currentTaskId) return;

        try {
            await this.cancelCrawl(this.currentTaskId);
            
            if (this.progressInterval) {
                clearInterval(this.progressInterval);
                this.progressInterval = null;
            }

            this.state.isLoading = false;
            this.currentTaskId = null;
            
            document.getElementById('startCrawlBtn').classList.remove('loading');
            document.getElementById('progressSection').style.display = 'none';
            
            this.state.addLog('爬取任务已取消', 'warning');
            this.notification.show('爬取任务已取消', 'warning');

        } catch (error) {
            console.error('取消爬取失败:', error);
            this.notification.show('取消爬取失败', 'error');
        }
    }

    // 取消爬取（模拟实现）
    async cancelCrawl(taskId) {
        await new Promise(resolve => setTimeout(resolve, 500));
        return { success: true };
    }

    // 设置模拟数据（开发阶段）
    setupMockData() {
        // 可以在这里设置一些测试数据
        console.log('Ensemble Stars Music 卡面爬取工具已初始化');
    }
}

// 页面加载完成后初始化应用
document.addEventListener('DOMContentLoaded', () => {
    window.app = new EnsembleStarsApp();
});

// 添加一些实用的CSS样式到预览区域
const previewStyles = `
<style>
.event-preview {
    text-align: center;
    padding: 2rem;
}

.event-preview h3 {
    font-size: 1.5rem;
    font-weight: 600;
    color: var(--gray-800);
    margin-bottom: 1rem;
}

.event-preview .event-date {
    color: var(--primary-color);
    font-weight: 500;
    margin-bottom: 1rem;
}

.event-preview .event-description {
    color: var(--gray-600);
    margin-bottom: 2rem;
    line-height: 1.6;
}

.event-actions {
    display: flex;
    justify-content: center;
}

.preview-btn {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.75rem 1.5rem;
    background: var(--primary-color);
    color: white;
    border: none;
    border-radius: var(--radius-md);
    cursor: pointer;
    transition: all var(--transition-fast);
    text-decoration: none;
}

.preview-btn:hover {
    background: var(--primary-hover);
    transform: translateY(-2px);
}
</style>
`;

// 将样式添加到head中
document.head.insertAdjacentHTML('beforeend', previewStyles);