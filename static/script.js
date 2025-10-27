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
    updateProgress(current, total, currentTask = '', percentage = null) {
        this.crawlProgress.current = current;
        this.crawlProgress.total = total;
        
        // 如果提供了具体的百分比，使用它；否则根据current/total计算
        if (percentage !== null) {
            this.crawlProgress.percentage = Math.round(percentage);
        } else {
            this.crawlProgress.percentage = total > 0 ? Math.round((current / total) * 100) : 0;
        }
        
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
        // 根据当前环境动态设置baseUrl
        // 开发环境使用/api，生产环境（通过Nginx代理）使用/es/api
        // 简单检测：如果是localhost或127.0.0.1，则为开发环境
        const isLocalhost = window.location.hostname === 'localhost' || 
                           window.location.hostname === '127.0.0.1' ||
                           window.location.hostname === '0.0.0.0';
        this.baseUrl = isLocalhost ? '/api' : '/es/api';
    }

    // 分析目录页
    async analyzeDirectory(url) {
        try {
            const response = await fetch(`${this.baseUrl}/analyze`, {
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

    // 开始爬取（调用真实后端）
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
        this.lastProcessedLogIndex = 0;
        this.currentDownloadUrl = null; // 保存当前任务的下载URL

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
        this.setupValidation();
    }

    // 绑定事件监听器
    bindEvents() {
        // 绑定事件监听器
        document.getElementById('urlInput').addEventListener('input', this.handleUrlInput.bind(this));
        document.getElementById('analyzeBtn').addEventListener('click', this.handleAnalyze.bind(this));
        document.getElementById('useDefaultBtn').addEventListener('click', this.handleUseDefault.bind(this));

        // 活动页事件
        const backBtn = document.getElementById('backBtn');
        if (backBtn) {
            backBtn.addEventListener('click', () => {
                this.state.switchPage('start');
            });
        }

        const selectAllBtn = document.getElementById('selectAllBtn');
        if (selectAllBtn) {
            selectAllBtn.addEventListener('click', () => {
                this.state.selectAllEvents();
            });
        }

        const clearAllBtn = document.getElementById('clearAllBtn');
        if (clearAllBtn) {
            clearAllBtn.addEventListener('click', () => {
                this.state.clearAllEvents();
            });
        }

        const eventSearch = document.getElementById('eventSearch');
        if (eventSearch) {
            eventSearch.addEventListener('input', () => {
                this.state.updateEventDisplay();
            });
        }

        const startCrawlBtn = document.getElementById('startCrawlBtn');
        if (startCrawlBtn) {
            startCrawlBtn.addEventListener('click', this.handleStartCrawl.bind(this));
        }

        const cancelCrawlBtn = document.getElementById('cancelCrawlBtn');
        if (cancelCrawlBtn) {
            cancelCrawlBtn.addEventListener('click', this.handleReturnToMain.bind(this));
        }

        // 事件列表点击事件（事件委托）
        const eventList = document.getElementById('eventList');
        if (eventList) {
            eventList.addEventListener('click', this.handleEventClick.bind(this));
        }

        // 通知关闭事件
        const notificationClose = document.querySelector('.notification-close');
        if (notificationClose) {
            notificationClose.addEventListener('click', () => {
                this.notification.hide();
            });
        }
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
                feedback.textContent = '💡 可直接点击"分析目录页"使用默认链接，或点击"默认"按钮快速填入';
                feedback.className = 'input-feedback';
                analyzeBtn.disabled = false; // 允许使用默认链接
            } else if (isValid) {
                feedback.textContent = '✓ 链接格式正确，可以开始分析';
                feedback.className = 'input-feedback success';
                analyzeBtn.disabled = false;
            } else {
                feedback.textContent = '✗ 请输入有效的Gamerch链接（ensemble-star-music相关页面）';
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

    // 处理使用默认链接按钮
    handleUseDefault() {
        const urlInput = document.getElementById('urlInput');
        const defaultUrl = 'https://gamerch.com/ensemble-star-music/895943';
        
        urlInput.value = defaultUrl;
        urlInput.dispatchEvent(new Event('input')); // 触发验证
        
        // 添加视觉反馈
        this.notification.show('已填入默认链接', 'success');
        
        // 聚焦到输入框
        urlInput.focus();
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

            if (result.success) {
                if (result.session_id) {
                    // 使用Redis缓存方式
                    this.notification.show(`分析完成！找到 ${result.events_count} 个活动`, 'success');
                    
                    // 跳转到活动列表页面，传递会话ID
                    setTimeout(() => {
                        window.location.href = this.getPageUrl(`/events?session_id=${result.session_id}`);
                    }, 1500);
                } else if (result.events && result.events.length > 0) {
                    // 回退到原始方式（Redis不可用时）
                    this.notification.show(`分析完成！找到 ${result.events.length} 个活动`, 'success');
                    
                    // 跳转到活动列表页面，传递活动数据
                    setTimeout(() => {
                        const eventsParam = encodeURIComponent(JSON.stringify(result.events));
                        window.location.href = this.getPageUrl(`/events?events=${eventsParam}`);
                    }, 1500);
                } else {
                    this.notification.show('未找到符合条件的活动', 'warning');
                }
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

    // 分析目录页
    async analyzeDirectory(url) {
        return fetch(`${this.baseUrl}/analyze`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url })
        }).then(r => r.json());
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

            // 隐藏下载按钮
            const downloadBtn = document.getElementById('downloadProgressBtn');
            if (downloadBtn) {
                downloadBtn.style.display = 'none';
                downloadBtn.classList.remove('pulse');
            }

            // 初始化进度
            this.state.crawlProgress.startTime = Date.now();
            this.state.crawlProgress.logs = [];
            this.lastProcessedLogIndex = 0;
            this.state.updateProgress(0, this.state.selectedEvents.size, '准备开始爬取...');

            // 构建选中事件列表并调用真实后端
            const selectedIds = Array.from(this.state.selectedEvents);
            const events = this.state.events.filter(e => selectedIds.includes(e.id));
            const result = await this.api.startCrawl(events);

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

    // 开始进度监控（轮询后端进度）
    startProgressMonitoring() {
        const poll = async () => {
            if (!this.currentTaskId) return;
            try {
                const res = await this.api.getCrawlProgress(this.currentTaskId);
                if (!res.success) {
                    this.state.addLog(res.message || '获取进度失败', 'error');
                    return;
                }
    
                const p = res.progress || {};
                const current = p.current || 0;
                const total = p.total || 0;
                const currentTask = p.current_task || '';
                const percentage = p.percentage !== undefined ? p.percentage : null;
                console.debug('[Progress]', { status: res.status, current, total, percentage });
                
                // 使用后端提供的百分比（如果有）
                this.state.updateProgress(current, total, currentTask, percentage);
                
                // 当进度达到100%，提前显示禁用的下载按钮，避免视觉空窗
                const effectivePercent = percentage !== null 
                    ? Math.round(percentage) 
                    : (total > 0 ? Math.round((current / total) * 100) : null);
                if (effectivePercent !== null && effectivePercent >= 100) {
                    const downloadBtnEarly = document.getElementById('downloadProgressBtn');
                    if (downloadBtnEarly) {
                        console.debug('[UI] Early show download button, effectivePercent =', effectivePercent);
                        downloadBtnEarly.style.display = 'flex';
                        downloadBtnEarly.classList.add('pulse');
                        downloadBtnEarly.disabled = true;
                        downloadBtnEarly.title = '正在准备文件，请稍候...';
                    }
                }
                
                // 处理后端传来的日志
                if (res.logs && Array.isArray(res.logs)) {
                    // 获取最新的日志条目（避免重复显示）
                    const lastLogIndex = this.lastProcessedLogIndex || 0;
                    const newLogs = res.logs.slice(lastLogIndex);
                    
                    // 添加新的日志条目
                    for (const log of newLogs) {
                        if (log.message) {
                            this.state.addLog(log.message, log.type || 'info');
                        }
                    }
                    
                    // 更新已处理的日志索引
                    this.lastProcessedLogIndex = res.logs.length;
                }
    
                if (res.status === 'completed' && res.resultFile) {
                    clearInterval(this.progressInterval);
                    this.progressInterval = null;
                    this.state.isLoading = false;
                    this.state.addLog('所有活动处理完成', 'success');
                    this.state.addLog('Excel文件生成完成', 'success');
                    document.getElementById('startCrawlBtn').classList.remove('loading');

                    // 保存下载URL（优先使用后端返回的URL）
                    this.currentDownloadUrl = res.download_url;

                    // 显示进度区域的下载按钮
                    const downloadBtn = document.getElementById('downloadProgressBtn');
                    if (downloadBtn) {
                        console.debug('[UI] Enable download button for task', this.currentTaskId);
                        downloadBtn.style.display = 'flex';
                        downloadBtn.classList.add('pulse');
                        downloadBtn.disabled = false;
                        downloadBtn.title = '下载';
                        // 移除旧的事件监听器并添加新的
                        downloadBtn.onclick = null;
                        downloadBtn.onclick = () => this.downloadExcelWithUrl();
                    }

                    // 显示下载兜底按钮（防止浏览器阻止自动下载）
                    const fb = document.getElementById('downloadFallback');
                    const fblink = document.getElementById('downloadFallbackLink');
                    if (fb && fblink) {
                        fblink.href = this.currentDownloadUrl;
                        fb.style.display = 'block';
                        // 添加醒目的样式
                        fb.style.animation = 'pulse 2s infinite';
                        fb.style.border = '2px solid #007bff';
                        fb.style.borderRadius = '8px';
                        fb.style.padding = '16px';
                        fb.style.backgroundColor = '#f8f9fa';
                    }

                    // 添加明显的下载提示日志
                    this.state.addLog('📥 文件已准备就绪，请点击上方下载按钮获取Excel文件', 'success');
                    
                    // 移除自动跳转，让用户可以持续查看日志和下载文件
                    this.notification.show('爬取完成！请点击下载按钮获取Excel文件。', 'success', 10000);
                } else if (res.status === 'failed') {
                    clearInterval(this.progressInterval);
                    this.progressInterval = null;
                    this.state.isLoading = false;
                    document.getElementById('startCrawlBtn').classList.remove('loading');
                    
                    // 隐藏下载按钮
                    const downloadBtn = document.getElementById('downloadProgressBtn');
                    if (downloadBtn) {
                        downloadBtn.style.display = 'none';
                        downloadBtn.classList.remove('pulse');
                    }
                    
                    this.notification.show(`爬取失败：${res.errorMessage || '未知错误'}`, 'error');
                } else if (res.status === 'cancelled') {
                    clearInterval(this.progressInterval);
                    this.progressInterval = null;
                    this.state.isLoading = false;
                    document.getElementById('startCrawlBtn').classList.remove('loading');
                    
                    // 隐藏下载按钮
                    const downloadBtn = document.getElementById('downloadProgressBtn');
                    if (downloadBtn) {
                        downloadBtn.style.display = 'none';
                        downloadBtn.classList.remove('pulse');
                    }
                    
                    this.notification.show('爬取任务已取消', 'warning');
                }
            } catch (error) {
                console.error('获取进度失败:', error);
            }
        };
    
        if (this.progressInterval) {
            clearInterval(this.progressInterval);
            this.progressInterval = null;
        }
    
        this.progressInterval = setInterval(poll, 2000);
        poll();
    }

    // 完成爬取
    completeCrawl() {
        if (this.progressInterval) {
            clearInterval(this.progressInterval);
            this.progressInterval = null;
        }

        this.state.isLoading = false;
        this.state.addLog('所有活动处理完成', 'success');
        
        // 真实的爬取完成处理由events.js中的轮询机制处理
        document.getElementById('startCrawlBtn').classList.remove('loading');
    }

    // 下载Excel文件
    downloadExcel() {
        if (!this.currentDownloadUrl) {
            this.state.addLog('无法下载：下载链接不存在', 'error');
            return;
        }

        // 创建下载链接并触发下载
        const link = document.createElement('a');
        link.href = this.currentDownloadUrl;
        link.style.display = 'none';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        this.state.addLog('开始下载Excel文件...', 'success');
    }

    // 使用保存的下载URL下载Excel文件
    downloadExcelWithUrl() {
        if (!this.currentDownloadUrl) {
            this.state.addLog('无法下载：下载链接不存在', 'error');
            return;
        }

        // 创建下载链接并触发下载
        const link = document.createElement('a');
        link.href = this.currentDownloadUrl;
        link.style.display = 'none';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        this.state.addLog('开始下载Excel文件...', 'success');
    }

    // 处理取消爬取
    async handleCancelCrawl() {
        if (!this.currentTaskId) return;

        try {
            await this.api.cancelCrawl(this.currentTaskId);
            
            if (this.progressInterval) {
                clearInterval(this.progressInterval);
                this.progressInterval = null;
            }

            this.state.isLoading = false;
            this.currentTaskId = null;
            
            document.getElementById('startCrawlBtn').classList.remove('loading');
            document.getElementById('progressSection').style.display = 'none';
            
            // 隐藏下载按钮
            const downloadBtn = document.getElementById('downloadProgressBtn');
            if (downloadBtn) {
                downloadBtn.style.display = 'none';
                downloadBtn.classList.remove('pulse');
            }
            
            this.state.addLog('爬取任务已取消', 'warning');
            this.notification.show('爬取任务已取消', 'warning');

        } catch (error) {
            console.error('取消爬取失败:', error);
            this.notification.show('取消爬取失败', 'error');
        }
    }

    // 返回主页面
    handleReturnToMain() {
        // 隐藏进度区域
        document.getElementById('progressSection').style.display = 'none';
        
        // 重置开始按钮状态
        const startBtn = document.getElementById('startCrawlBtn');
        startBtn.classList.remove('loading');
        startBtn.disabled = false;
        
        // 隐藏下载按钮
        const downloadBtn = document.getElementById('downloadProgressBtn');
        if (downloadBtn) {
            downloadBtn.style.display = 'none';
            downloadBtn.classList.remove('pulse');
        }
        
        // 清理进度监控
        if (this.progressInterval) {
            clearInterval(this.progressInterval);
            this.progressInterval = null;
        }
        
        // 重置状态
        this.state.isLoading = false;
        this.currentTaskId = null;
        
        this.state.addLog('已返回主页面', 'info');
    }

    // 取消爬取
    async cancelCrawl(taskId) {
        try {
            const response = await fetch(`${this.baseUrl}/cancel/${taskId}`, {
                method: 'POST'
            });
            return await response.json();
        } catch (error) {
            console.error('取消爬取失败:', error);
            return { success: false, error: error.message };
        }
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