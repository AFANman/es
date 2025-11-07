/**
 * 活动列表页面JavaScript
 * 处理活动列表的显示、选择、搜索和爬取功能
 */

// API 服务类
class ApiService {
    constructor() {
        // 根据当前环境动态设置baseUrl
        const isLocalhost = window.location.hostname === 'localhost' || 
                           window.location.hostname === '127.0.0.1' ||
                           window.location.hostname === '0.0.0.0';
        this.baseUrl = isLocalhost ? '/api' : '/es/api';
    }

    // 从Redis获取活动数据
    async getEventsFromCache(sessionId) {
        try {
            const response = await fetch(`${this.baseUrl}/events/${sessionId}`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                }
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('获取活动数据失败:', error);
            throw error;
        }
    }

    // 开始爬取
    async startCrawl(events) {
        try {
            const response = await fetch(`${this.baseUrl}/crawl/start`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ events })
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

    // 获取任务列表
    async getTasks() {
        try {
            const response = await fetch(`${this.baseUrl}/tasks`);
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('获取任务列表失败:', error);
            throw error;
        }
    }
}

class EventsPage {
    constructor() {
        this.events = [];
        this.selectedEvents = new Set();
        this.currentTask = null;
        this.progressInterval = null;
        this.pullRefreshEnabled = false;
        this.pullStartY = 0;
        this.pullCurrentY = 0;
        this.isPulling = false;
        this.pullThreshold = 80;
        this.api = new ApiService();
        this.isDownloading = false;
        
        this.init();
    }

    // 根据环境动态生成页面URL
    getPageUrl(path) {
        const isLocalhost = window.location.hostname === 'localhost' || 
                           window.location.hostname === '127.0.0.1' ||
                           window.location.hostname === '0.0.0.0';
        return isLocalhost ? path : `/es${path}`;
    }

    init() {
        this.bindEvents();
        this.loadEvents();
        this.initPullRefresh();
        this.checkCompletedTask();
    }

    bindEvents() {
        // 返回首页按钮
        document.getElementById('backToHomeBtn').addEventListener('click', () => {
            window.location.href = this.getPageUrl('/');
        });

        // 全选/清空按钮
        document.getElementById('selectAllBtn').addEventListener('click', () => {
            this.selectAllEvents();
        });

        document.getElementById('clearAllBtn').addEventListener('click', () => {
            this.clearAllEvents();
        });

        // 搜索功能
        document.getElementById('eventSearch').addEventListener('input', (e) => {
            this.filterEvents(e.target.value);
        });

        // 开始爬取按钮
        document.getElementById('startCrawlBtn').addEventListener('click', () => {
            this.startCrawl();
        });

        // 返回按钮
        document.getElementById('cancelCrawlBtn').addEventListener('click', () => {
            this.returnToMain();
        });

        // 立即下载按钮（确保不会重复绑定）
        const downloadProgressBtn = document.getElementById('downloadProgressBtn');
        if (downloadProgressBtn) {
            downloadProgressBtn.onclick = null;
            downloadProgressBtn.onclick = () => this.downloadResult();
        }

        // 通知关闭按钮
        const notificationCloseBtn = document.querySelector('.notification-close');
        if (notificationCloseBtn) {
            notificationCloseBtn.addEventListener('click', () => {
                this.hideNotification();
            });
        }
    }

    // 初始化下拉刷新功能
    initPullRefresh() {
        const eventList = document.getElementById('eventList');
        const pullIndicator = document.getElementById('pullRefreshIndicator');

        eventList.addEventListener('touchstart', (e) => {
            if (eventList.scrollTop === 0) {
                this.pullStartY = e.touches[0].clientY;
                this.pullRefreshEnabled = true;
            }
        }, { passive: true });

        eventList.addEventListener('touchmove', (e) => {
            if (!this.pullRefreshEnabled) return;

            this.pullCurrentY = e.touches[0].clientY;
            const pullDistance = this.pullCurrentY - this.pullStartY;

            if (pullDistance > 0 && eventList.scrollTop === 0) {
                e.preventDefault();
                this.isPulling = true;
                
                const progress = Math.min(pullDistance / this.pullThreshold, 1);
                pullIndicator.style.transform = `translateY(${pullDistance * 0.5}px)`;
                pullIndicator.style.opacity = progress;
                
                if (pullDistance >= this.pullThreshold) {
                    pullIndicator.innerHTML = '<i class="fas fa-sync-alt"></i><span>释放刷新</span>';
                    pullIndicator.classList.add('ready');
                } else {
                    pullIndicator.innerHTML = '<i class="fas fa-arrow-down"></i><span>下拉刷新</span>';
                    pullIndicator.classList.remove('ready');
                }
            }
        }, { passive: false });

        eventList.addEventListener('touchend', () => {
            if (this.isPulling) {
                const pullDistance = this.pullCurrentY - this.pullStartY;
                
                if (pullDistance >= this.pullThreshold) {
                    this.refreshEvents();
                }
                
                // 重置状态
                pullIndicator.style.transform = '';
                pullIndicator.style.opacity = '';
                pullIndicator.innerHTML = '<i class="fas fa-arrow-down"></i><span>下拉刷新</span>';
                pullIndicator.classList.remove('ready');
            }
            
            this.pullRefreshEnabled = false;
            this.isPulling = false;
        });

        // 鼠标事件支持（用于桌面测试）
        let isMouseDown = false;
        let mouseStartY = 0;

        eventList.addEventListener('mousedown', (e) => {
            if (eventList.scrollTop === 0) {
                isMouseDown = true;
                mouseStartY = e.clientY;
                this.pullRefreshEnabled = true;
            }
        });

        eventList.addEventListener('mousemove', (e) => {
            if (!isMouseDown || !this.pullRefreshEnabled) return;

            const pullDistance = e.clientY - mouseStartY;
            
            if (pullDistance > 0 && eventList.scrollTop === 0) {
                e.preventDefault();
                this.isPulling = true;
                
                const progress = Math.min(pullDistance / this.pullThreshold, 1);
                pullIndicator.style.transform = `translateY(${pullDistance * 0.5}px)`;
                pullIndicator.style.opacity = progress;
                
                if (pullDistance >= this.pullThreshold) {
                    pullIndicator.innerHTML = '<i class="fas fa-sync-alt"></i><span>释放刷新</span>';
                    pullIndicator.classList.add('ready');
                } else {
                    pullIndicator.innerHTML = '<i class="fas fa-arrow-down"></i><span>下拉刷新</span>';
                    pullIndicator.classList.remove('ready');
                }
            }
        });

        eventList.addEventListener('mouseup', (e) => {
            if (isMouseDown && this.isPulling) {
                const pullDistance = e.clientY - mouseStartY;
                
                if (pullDistance >= this.pullThreshold) {
                    this.refreshEvents();
                }
                
                // 重置状态
                pullIndicator.style.transform = '';
                pullIndicator.style.opacity = '';
                pullIndicator.innerHTML = '<i class="fas fa-arrow-down"></i><span>下拉刷新</span>';
                pullIndicator.classList.remove('ready');
            }
            
            isMouseDown = false;
            this.pullRefreshEnabled = false;
            this.isPulling = false;
        });
    }

    // 刷新活动列表
    async refreshEvents() {
        const pullIndicator = document.getElementById('pullRefreshIndicator');
        pullIndicator.innerHTML = '<i class="fas fa-sync-alt fa-spin"></i><span>刷新中...</span>';
        
        try {
            await this.loadEvents();
            this.showNotification('活动列表已刷新', 'success');
        } catch (error) {
            this.showNotification('刷新失败，请重试', 'error');
        }
        
        setTimeout(() => {
            pullIndicator.style.transform = '';
            pullIndicator.style.opacity = '';
            pullIndicator.innerHTML = '<i class="fas fa-arrow-down"></i><span>下拉刷新</span>';
            pullIndicator.classList.remove('ready');
        }, 500);
    }

    // 从URL参数或Redis加载活动数据
    async loadEvents() {
        const urlParams = new URLSearchParams(window.location.search);
        const sessionId = urlParams.get('session_id');
        const eventsData = urlParams.get('events');
        
        // 优先尝试从Redis获取数据（使用session_id）
        if (sessionId) {
            try {
                console.log('从Redis获取活动数据，会话ID:', sessionId);
                const result = await this.api.getEventsFromCache(sessionId);
                
                if (result.success && result.events) {
                    this.events = result.events;
                    this.renderEvents();
                    this.updateEventCount();
                    console.log('成功从Redis加载活动数据:', this.events.length, '个活动');
                    return;
                } else {
                    console.warn('从Redis获取活动数据失败:', result.message);
                    this.showErrorState('活动数据已过期，请重新分析目录页');
                    return;
                }
            } catch (error) {
                console.error('从Redis获取活动数据失败:', error);
                this.showErrorState('获取活动数据失败，请重新分析目录页');
                return;
            }
        }
        
        // 回退到原始方式（从URL参数获取）
        if (eventsData) {
            try {
                this.events = JSON.parse(decodeURIComponent(eventsData));
                this.renderEvents();
                this.updateEventCount();
                console.log('从URL参数加载活动数据:', this.events.length, '个活动');
                return;
            } catch (error) {
                console.error('解析活动数据失败:', error);
            }
        }
        
        // 如果没有任何数据源，显示空状态
        this.showEmptyState();
    }

    // 显示空状态
    showEmptyState() {
        const eventList = document.getElementById('eventList');
        eventList.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-calendar-times"></i>
                <p>暂无活动数据</p>
                <button onclick="window.location.href=eventsPage.getPageUrl('/')" class="btn-secondary">
                    返回首页重新分析
                </button>
            </div>
        `;
    }

    // 显示错误状态
    showErrorState(message) {
        const eventList = document.getElementById('eventList');
        eventList.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-exclamation-triangle"></i>
                <p>${message}</p>
                <button onclick="window.location.href=eventsPage.getPageUrl('/')" class="btn-secondary">
                    返回首页重新分析
                </button>
            </div>
        `;
    }

    // 渲染活动列表
    renderEvents() {
        const eventList = document.getElementById('eventList');
        
        if (this.events.length === 0) {
            this.showEmptyState();
            return;
        }

        eventList.innerHTML = this.events.map((event, index) => {
            const eventId = event.id || `event_${index}`;
            const eventName = event.title || event.name || '未知活动';
            const eventDate = event.date || '未知日期';
            const cardCount = event.cards ? event.cards.length : (event.card_count || 0);
            const eventType = event.type || '活动';
            const eventPath = event.path || '';
            const eventUrl = event.url || '';

            return `
            <div class="event-item" data-event-id="${eventId}">
                <div class="event-checkbox">
                    <input type="checkbox" id="event-${eventId}" ${this.selectedEvents.has(eventId) ? 'checked' : ''}>
                    <label for="event-${eventId}"></label>
                </div>
                <div class="event-content" onclick="eventsPage.toggleEventSelection('${eventId}')">
                    <div class="event-header">
                        <h4 class="event-title">${eventName}</h4>
                        <span class="event-date">${eventDate}</span>
                    </div>
                    <div class="event-details">
                        <span class="event-type">${eventType}</span>
                        <span class="event-cards">${cardCount} 张卡面</span>
                    </div>
                    <div class="preview-details">
                        ${eventPath ? `
                        <div class="detail-row">
                            <span class="label">路径:</span>
                            <span class="value">${eventPath}</span>
                        </div>
                        ` : ''}
                    </div>
                </div>
            </div>
            `;
        }).join('');

        // 绑定复选框事件
        eventList.querySelectorAll('input[type="checkbox"]').forEach(checkbox => {
            checkbox.addEventListener('change', (e) => {
                const eventId = e.target.id.replace('event-', '');
                if (e.target.checked) {
                    this.selectedEvents.add(eventId);
                } else {
                    this.selectedEvents.delete(eventId);
                }
                this.updateSelectedCount();
                this.updateCrawlButton();
            });
        });
    }

    // 切换活动选择状态
    toggleEventSelection(eventId) {
        const checkbox = document.getElementById(`event-${eventId}`);
        checkbox.checked = !checkbox.checked;
        checkbox.dispatchEvent(new Event('change'));
    }

    // 显示活动预览
    showEventPreview(eventId) {
        const event = this.events.find(e => (e.id || `event_${this.events.indexOf(e)}`) === eventId);
        if (!event) return;

        const eventName = event.title || event.name || '未知活动';
        const eventDate = event.date || '未知日期';
        const eventType = event.type || '活动';
        const cardCount = event.cards ? event.cards.length : (event.card_count || 0);
        const eventPath = event.path || '未知路径';

        const previewContent = document.getElementById('previewContent');
        previewContent.innerHTML = `
            <div class="preview-event">
                <div class="preview-header-info">
                    <h3>${eventName}</h3>
                    <span class="preview-date">${eventDate}</span>
                </div>
                <div class="preview-details">
                    <div class="detail-row">
                        <span class="label">活动类型:</span>
                        <span class="value">${eventType}</span>
                    </div>
                    <div class="detail-row">
                        <span class="label">卡面数量:</span>
                        <span class="value">${cardCount} 张</span>
                    </div>
                    <div class="detail-row">
                        <span class="label">描述:</span>
                        <span class="value">${event.description || '无描述'}</span>
                    </div>
                </div>
                ${event.cards && event.cards.length > 0 ? `
                    <div class="preview-cards">
                        <h4>卡面列表</h4>
                        <div class="cards-grid">
                            ${event.cards.slice(0, 6).map(card => `
                                <div class="card-item">
                                    <span class="card-name">${card.name || '未知卡面'}</span>
                                </div>
                            `).join('')}
                            ${event.cards.length > 6 ? `
                                <div class="card-item more">
                                    +${event.cards.length - 6} 更多
                                </div>
                            ` : ''}
                        </div>
                    </div>
                ` : ''}
            </div>
        `;
    }

    // 全选活动
    selectAllEvents() {
        this.events.forEach(event => {
            this.selectedEvents.add(event.id);
            const checkbox = document.getElementById(`event-${event.id}`);
            if (checkbox) checkbox.checked = true;
        });
        this.updateSelectedCount();
        this.updateCrawlButton();
    }

    // 清空选择
    clearAllEvents() {
        this.selectedEvents.clear();
        document.querySelectorAll('#eventList input[type="checkbox"]').forEach(checkbox => {
            checkbox.checked = false;
        });
        this.updateSelectedCount();
        this.updateCrawlButton();
    }

    // 过滤活动
    filterEvents(searchTerm) {
        const eventItems = document.querySelectorAll('.event-item');
        const term = searchTerm.toLowerCase();

        eventItems.forEach(item => {
            const title = item.querySelector('.event-title').textContent.toLowerCase();
            const type = item.querySelector('.event-type').textContent.toLowerCase();
            const date = item.querySelector('.event-date').textContent.toLowerCase();

            if (title.includes(term) || type.includes(term) || date.includes(term)) {
                item.style.display = '';
            } else {
                item.style.display = 'none';
            }
        });
    }

    // 更新活动数量显示
    updateEventCount() {
        document.getElementById('eventCount').textContent = `${this.events.length} 个活动`;
    }

    // 更新选中数量显示
    updateSelectedCount() {
        const summaryEl = document.getElementById('actionSummary');
        if (summaryEl) {
            summaryEl.textContent = this.selectedEvents.size > 0 
                ? `已选择 ${this.selectedEvents.size} 个活动` 
                : '请选择要爬取的活动';
        }
    }

    // 更新爬取按钮状态
    updateCrawlButton() {
        const crawlBtn = document.getElementById('startCrawlBtn');
        crawlBtn.disabled = this.selectedEvents.size === 0;
    }

    // 开始爬取
    async startCrawl() {
        console.log('开始爬取任务...');
        
        if (this.selectedEvents.size === 0) {
            console.log('未选择活动');
            this.showNotification('请先选择要爬取的活动', 'warning');
            return;
        }

        const selectedEventsList = this.events.filter(event => this.selectedEvents.has(event.id));
        console.log('选中的活动:', selectedEventsList);
        
        // 禁用爬取按钮
        const startBtn = document.getElementById('startCrawlBtn');
        // if (startBtn) {
        //     startBtn.disabled = true;
        //     startBtn.textContent = '启动中...';
        // }
        
        try {
            console.log('发送爬取请求...');
            const result = await this.api.startCrawl(selectedEventsList);
            console.log('响应结果:', result);
            
            if (result.success) {
                this.currentTask = result.taskId;
                console.log('任务ID:', this.currentTask);
                this.showProgressSection();
                this.startProgressMonitoring();
                this.showNotification('爬取任务已开始', 'success');
            } else {
                console.error('启动失败:', result.message);
                this.showNotification(result.message || '启动爬取失败', 'error');
                // 重新启用按钮
                if (startBtn) {
                    startBtn.disabled = false;
                    startBtn.textContent = '开始爬取';
                }
            }
        } catch (error) {
            console.error('启动爬取失败:', error);
            this.showNotification('启动爬取失败，请重试', 'error');
            // 重新启用按钮
            if (startBtn) {
                startBtn.disabled = false;
                startBtn.textContent = '开始爬取';
            }
        }
    }

    // 显示进度区域
    showProgressSection() {
        // 清空之前的日志
        this.allLogs = [];
        this.logKeys = new Set();
        const logContainer = document.getElementById('logContainer');
        if (logContainer) {
            logContainer.innerHTML = '';
        }
        
        document.getElementById('actionDefault').style.display = 'none';
        document.getElementById('progressSection').style.display = 'block';
    }

    // 隐藏进度区域
    hideProgressSection() {
        document.getElementById('progressSection').style.display = 'none';
        document.getElementById('actionDefault').style.display = 'flex';
        document.getElementById('startCrawlBtn').disabled = false;
    }

    // 开始进度监控
    startProgressMonitoring() {
        if (this.progressInterval) {
            clearInterval(this.progressInterval);
        }

        this.progressInterval = setInterval(() => {
            this.updateProgress();
        }, 1000);
    }

    // 更新进度
    async updateProgress() {
        if (!this.currentTask) return;

        try {
            const progress = await this.api.getCrawlProgress(this.currentTask);

            this.updateProgressDisplay(progress);

            if (progress.status === 'completed' || progress.status === 'failed') {
                clearInterval(this.progressInterval);
                this.progressInterval = null;
                
                if (progress.status === 'completed') {
                    this.handleCrawlComplete(progress);
                } else {
                    this.handleCrawlFailed(progress);
                }
            }
        } catch (error) {
            console.error('获取进度失败:', error);
        }
    }

    // 更新进度显示
    updateProgressDisplay(progress) {
        const progressFill = document.getElementById('progressFill');
        const progressText = document.getElementById('progressText');
        const currentTask = document.getElementById('currentTask');
        const completedCount = document.getElementById('completedCount');
        const totalCount = document.getElementById('totalCount');
        const estimatedTime = document.getElementById('estimatedTime');

        // 正确访问后端返回的进度数据结构
        const progressData = progress.progress || {};
        const percentage = progressData.percentage || 0;
        
        progressFill.style.width = `${percentage}%`;
        progressText.textContent = `${Math.round(percentage)}%`;
        currentTask.textContent = progressData.current_task || '处理中...';
        completedCount.textContent = progressData.current || 0;
        totalCount.textContent = progressData.total || 0;
        
        // 计算预估时间
        if (progressData.start_time && progressData.current > 0) {
            const startTime = new Date(progressData.start_time);
            const now = new Date();
            const elapsed = (now - startTime) / 1000; // 秒
            const avgTimePerItem = elapsed / progressData.current;
            const remaining = progressData.total - progressData.current;
            const estimatedSeconds = Math.round(avgTimePerItem * remaining);
            
            if (estimatedSeconds > 0) {
                const minutes = Math.floor(estimatedSeconds / 60);
                const seconds = estimatedSeconds % 60;
                estimatedTime.textContent = `${minutes}分${seconds}秒`;
            } else {
                estimatedTime.textContent = '即将完成';
            }
        } else {
            estimatedTime.textContent = '计算中...';
        }

        // 更新日志
        if (progressData.logs && progressData.logs.length > 0) {
            this.updateLogs(progressData.logs);
        }
    }

    // 更新日志显示
    updateLogs(logs) {
        const logContainer = document.getElementById('logContainer');
        if (!logContainer) {
            console.warn('[Logs] logContainer not found; skipping log update.');
            return;
        }
        
        // 如果没有已存储的日志，初始化
        if (!this.allLogs) {
            this.allLogs = [];
        }
        
        // 添加新日志到累积列表中（避免重复）
        if (logs && logs.length > 0) {
            for (const log of logs) {
                // 简单的重复检查：基于时间和消息内容
                const logKey = `${log.time || ''}_${log.message || ''}`;
                if (!this.logKeys) {
                    this.logKeys = new Set();
                }
                
                if (!this.logKeys.has(logKey)) {
                    this.allLogs.push(log);
                    this.logKeys.add(logKey);
                }
            }
        }
        
        // 渲染所有累积的日志
        logContainer.innerHTML = this.allLogs.map(log => `
            <div class="log-item ${log.level || 'info'}">
                <span class="log-time">${log.time || ''}</span>
                <span class="log-message">${log.message || ''}</span>
            </div>
        `).join('');
        
        // 自动滚动到底部
        logContainer.scrollTop = logContainer.scrollHeight;
    }

    // 处理爬取完成
    handleCrawlComplete(progress) {
        this.showNotification('爬取完成！', 'success');
        
        // 显示下载按钮
        if (progress.download_url) {
            this.showDownloadButton(progress.download_url);
        }
        
        // 保存最后完成的任务信息，用于页面刷新后恢复
        localStorage.setItem('lastCompletedTask', JSON.stringify({
            taskId: this.currentTask,
            downloadUrl: progress.download_url,
            completedAt: new Date().toISOString()
        }));
        
        // 不再自动隐藏进度区域，让用户可以查看完整的日志
        // 只清空当前任务ID，但保持界面显示
        this.currentTask = null;
        
        // 停止进度监控
        if (this.progressInterval) {
            clearInterval(this.progressInterval);
            this.progressInterval = null;
        }
    }

    // 处理爬取失败
    handleCrawlFailed(progress) {
        this.showNotification(progress.error || '爬取失败', 'error');
        setTimeout(() => {
            this.hideProgressSection();
            this.currentTask = null;
        }, 3000);
    }

    // 显示下载按钮
    showDownloadButton(downloadUrl) {
        // 保存下载URL
        this.downloadUrl = downloadUrl;
        
        // 显示立即下载按钮
        const downloadBtn = document.getElementById('downloadProgressBtn');
        if (downloadBtn) {
            downloadBtn.style.display = 'inline-flex';
            downloadBtn.classList.add('pulse');
        }
        
        // 在日志中添加下载提示
        this.updateLogs([{
            level: 'success',
            time: new Date().toLocaleTimeString(),
            message: '📥 文件已准备就绪！请点击"立即下载"按钮获取文件'
        }]);
    }

    // 下载结果文件
    async downloadResult() {
        // 防止并发或重复触发导致多次下载
        if (this.isDownloading) {
            console.warn('下载正在进行中，已忽略重复点击');
            return;
        }

        this.isDownloading = true;
        if (!this.downloadUrl) {
            this.showNotification('下载链接不可用', 'error');
            this.isDownloading = false;
            return;
        }
        
        console.log("开始下载文件，下载链接:", this.downloadUrl);
        
        try {
            // 先通过 fetch 检查响应
            console.log("发送下载请求...");
            const response = await fetch(this.downloadUrl);
            
            console.log("响应状态:", response.status);
            console.log("响应头:", Object.fromEntries(response.headers.entries()));
            
            if (!response.ok) {
                // 如果响应不成功，尝试读取错误信息
                const errorText = await response.text();
                console.error("下载请求失败:", errorText);
                
                try {
                    const errorJson = JSON.parse(errorText);
                    this.showNotification(`下载失败: ${errorJson.message || '未知错误'}`, 'error');
                } catch (e) {
                    this.showNotification(`下载失败: HTTP ${response.status}`, 'error');
                }
                return;
            }
            
            // 检查响应类型
            const contentType = response.headers.get('content-type');
            console.log("Content-Type:", contentType);
            
            if (contentType && contentType.includes('application/json')) {
                // 如果返回的是JSON，说明有错误
                const errorData = await response.json();
                console.error("服务器返回JSON错误:", errorData);
                this.showNotification(`下载失败: ${errorData.message || '服务器返回了错误响应'}`, 'error');
                return;
            }
            
            // 获取文件名
            const contentDisposition = response.headers.get('content-disposition');
            let filename = 'download.xlsx';
            if (contentDisposition) {
                const filenameMatch = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
                if (filenameMatch && filenameMatch[1]) {
                    filename = filenameMatch[1].replace(/['"]/g, '');
                }
            }
            console.log("文件名:", filename);
            
            // 获取文件数据
            const blob = await response.blob();
            console.log("文件大小:", blob.size, "bytes");
            console.log("文件类型:", blob.type);
            
            // 创建下载链接
            const url = window.URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = filename;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            
            // 清理临时URL
            window.URL.revokeObjectURL(url);
            
            this.showNotification('文件下载成功', 'success');
            console.log("文件下载完成");
            
        } catch (error) {
            console.error("下载过程中发生错误:", error);
            this.showNotification(`下载失败: ${error.message}`, 'error');
        } finally {
            this.isDownloading = false;
        }
    }

    // 取消爬取
    // 返回主页面
    returnToMain() {
        // 隐藏进度区域，回到开始爬取页面
        this.hideProgressSection();
        
        // 清理进度监控
        if (this.progressInterval) {
            clearInterval(this.progressInterval);
            this.progressInterval = null;
        }
        
        // 隐藏下载按钮
        const downloadBtn = document.getElementById('downloadProgressBtn');
        if (downloadBtn) {
            downloadBtn.style.display = 'none';
        }
        
        this.showNotification('已返回主页面', 'info');
    }

    async cancelCrawl() {
        if (!this.currentTask) return;

        try {
            const result = await this.api.cancelCrawl(this.currentTask);
            
            if (result.success) {
                this.showNotification('爬取已取消', 'info');
                clearInterval(this.progressInterval);
                this.progressInterval = null;
                this.hideProgressSection();
                this.currentTask = null;
            } else {
                this.showNotification('取消失败', 'error');
            }
        } catch (error) {
            console.error('取消爬取失败:', error);
            this.showNotification('取消失败，请重试', 'error');
        }
    }

    // 显示通知
    showNotification(message, type = 'info') {
        const notification = document.getElementById('notification');
        const messageEl = notification.querySelector('.notification-message');
        const iconEl = notification.querySelector('.notification-icon');

        messageEl.textContent = message;
        
        // 设置图标
        const icons = {
            success: 'fas fa-check-circle',
            error: 'fas fa-exclamation-circle',
            warning: 'fas fa-exclamation-triangle',
            info: 'fas fa-info-circle'
        };
        
        iconEl.className = `notification-icon ${icons[type] || icons.info}`;
        notification.className = `notification ${type} show`;

        // 自动隐藏
        setTimeout(() => {
            this.hideNotification();
        }, 5000);
    }

    // 隐藏通知
    hideNotification() {
        const notification = document.getElementById('notification');
        notification.classList.remove('show');
    }

    // 检查是否有已完成的任务并显示下载按钮
    async checkCompletedTask() {
        try {
            // 检查localStorage中是否有最近完成的任务
            const lastCompletedTaskStr = localStorage.getItem('lastCompletedTask');
            if (lastCompletedTaskStr) {
                const lastCompletedTask = JSON.parse(lastCompletedTaskStr);
                const completedAt = new Date(lastCompletedTask.completedAt);
                const now = new Date();
                
                // 如果任务是在24小时内完成的，显示下载按钮
                if (now - completedAt < 24 * 60 * 60 * 1000) {
                    // 验证任务是否仍然有效
                    try {
                        const progress = await this.api.getCrawlProgress(lastCompletedTask.taskId);
                        if (progress.success && progress.status === 'completed' && progress.download_url) {
                            this.showDownloadButton(progress.download_url);
                        }
                    } catch (error) {
                        console.error('验证任务失败:', error);
                    }
                }
            }
            
            // 同时检查是否有其他已完成的任务
            try {
                const tasksData = await this.api.getTasks();
                if (tasksData.success && tasksData.tasks && tasksData.tasks.length > 0) {
                    // 找到最新的已完成任务
                    const completedTasks = tasksData.tasks.filter(task => task.status === 'completed');
                    if (completedTasks.length > 0) {
                        const latestTask = completedTasks[completedTasks.length - 1];
                        try {
                            const progress = await this.api.getCrawlProgress(latestTask.taskId);
                            if (progress.success && progress.download_url) {
                                this.showDownloadButton(progress.download_url);
                            }
                        } catch (error) {
                            console.error('获取任务进度失败:', error);
                        }
                    }
                }
            } catch (error) {
                console.error('获取任务列表失败:', error);
            }
        } catch (error) {
            console.error('检查已完成任务失败:', error);
        }
    }
}

// 初始化页面
let eventsPage;
document.addEventListener('DOMContentLoaded', () => {
    eventsPage = new EventsPage();
    eventsPage.init();
    window.eventsPage = eventsPage; // 添加到全局作用域以便调试
});