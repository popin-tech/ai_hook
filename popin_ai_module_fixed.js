/**
 * Popin AI Module (v1.4)
 */

; (function () {
    'use strict';

    // 檢測是否在 iframe 中執行，如果是則停止執行 (防止在 popIn 廣告 iframe 內重複執行)
    try {
        if (window.self !== window.top) {
            // Popin AI Module: Iframe detected, stopping execution
            return;
        }
    } catch (e) {
        // 若因跨網域導致存取 window.top 失敗，通常也代表在 iframe 中
        return;
    }

    // ===========================================
    // 防止重複執行 (Singleton Pattern)
    // ===========================================
    if (window.PopinAIModuleInitialized) {
        return;
    }
    window.PopinAIModuleInitialized = true;

    // ===========================================
    // 配置選項 - 媒體商可依需求調整
    // ===========================================
    var config = {
        // 是否啟用模擬模式（當 API 無法使用時）
        enableMockMode: false,
        // API 端點 (新的統一 AI API)
        apiEndpoint: 'https://ai-ad-439393162392.asia-east1.run.app',
        // 第二頁 URL (請媒體商調整為實際的第二頁路徑)
        secondPageUrl: 'test_page2_1104.html',
        // 標題顯示容器選擇器 (請媒體商調整為實際的標題容器)
        titleSelector: '#popin_article_title',
        // 第一頁標題提取選擇器 (請媒體商調整為實際的標題選擇器)
        firstPageTitleSelector: 'div.news_info > div.title > p.name',
        // 模擬延遲時間（毫秒）
        mockDelay: 2000,
        // 除錯模式
        debugMode: true
    };

    // ===========================================
    // CSS 樣式注入 (使用原始 CSS 檔案的完整樣式)
    // ===========================================
    function injectCSS() {
        var css = [
            '#popin_recommend_ai {',
            '  background-color: rgba(222, 241, 234, 0.5);',
            '  border-radius: 8px;',
            '  padding: 16px;',
            '  margin-bottom: 15px;',
            '  position: relative;',
            '  overflow: hidden;',
            '  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;',
            '}',
            '',
            '.ai-recommend-header {',
            '  display: flex;',
            '  align-items: center;',
            '  margin-bottom: 16px;',
            '  color: #006A7C;',
            '  font-weight: bold;',
            '  font-size: 18px;',
            '}',
            '',
            '.ai-recommend-icon {',
            '  margin-right: 10px;',
            '  display: flex;',
            '  align-items: center;',
            '  position: relative;',
            '}',
            '',
            '.ai-recommend-title {',
            '  color: #006A7C;',
            '  font-weight: bold;',
            '  font-size: 1em;',
            '}',
            '',
            '.ai-recommend-list {',
            '  display: flex;',
            '  gap: 15px;',
            '  justify-content: space-between;',
            '}',
            '',
            '.ai-recommend-item {',
            '  background: #fff;',
            '  border-radius: 4px;',
            '  padding: 8px 16px;',
            '  flex: 1;',
            '  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);',
            '  color: #252525;',
            '  font-size: 1.125em;',
            '  line-height: 1.74;',
            '  text-decoration: none;',
            '  display: block;',
            '  border: 1px solid transparent;',
            '  transition: border-color 0.2s, color 0.2s;',
            '  position: relative;',
            '}',
            '',
            '.ai-recommend-item:hover {',
            '  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);',
            '  text-decoration: none;',
            '  color: #FF5C1A;',
            '  border: 1px solid #FFDED1;',
            '}',
            '',
            '@media (min-width: 1025px) {',
            '  .ai-recommend-item {',
            '    min-height: 112px;',
            '    padding: 8px 16px;',
            '    box-sizing: border-box;',
            '    overflow: hidden;',
            '  }',
            '',
            '  .ai-recommend-text {',
            '    display: -webkit-box;',
            '    -webkit-box-orient: vertical;',
            '    -webkit-line-clamp: 3;',
            '    line-clamp: 3;',
            '    overflow: hidden;',
            '    text-overflow: ellipsis;',
            '    word-break: break-all;',
            '    line-height: 1.5;',
            '  }',
            '}',
            '',
            '@media (max-width: 1024px) {',
            '  .ai-recommend-list {',
            '    flex-direction: column;',
            '  }',
            '',
            '  .ai-recommend-item {',
            '    min-height: 80px;',
            '    padding: 8px 16px;',
            '    box-sizing: border-box;',
            '    overflow: hidden;',
            '  }',
            '',
            '  .ai-recommend-text {',
            '    display: -webkit-box;',
            '    -webkit-box-orient: vertical;',
            '    -webkit-line-clamp: 2;',
            '    line-clamp: 2;',
            '    overflow: hidden;',
            '    text-overflow: ellipsis;',
            '    word-break: break-all;',
            '    line-height: 1.5;',
            '  }',
            '',
            '  .skeleton-item {',
            '    height: 80px;',
            '    min-height: 80px;',
            '  }',
            '}',
            '',
            '/* Loading Skeleton Styles */',
            '.ai-recommend-skeleton {',
            '  display: flex;',
            '  gap: 15px;',
            '  justify-content: space-between;',
            '  width: 100%;',
            '}',
            '',
            '.skeleton-item {',
            '  background: #fff;',
            '  border-radius: 4px;',
            '  padding: 12px 16px;',
            '  flex: 1;',
            '  height: 112px;',
            '  box-sizing: border-box;',
            '  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);',
            '  border: 1px solid #eee;',
            '  display: flex;',
            '  flex-direction: column;',
            '  justify-content: center;',
            '  gap: 10px;',
            '}',
            '',
            '.skeleton-line {',
            '  height: 12px;',
            '  background: #e0e0e0;',
            '  border-radius: 6px;',
            '  width: 100%;',
            '  animation: pulse 1.5s infinite ease-in-out;',
            '}',
            '',
            '@keyframes pulse {',
            '  0% { opacity: 0.5; }',
            '  50% { opacity: 1; }',
            '  100% { opacity: 0.5; }',
            '}',
            '',
            '@media (max-width: 1024px) {',
            '  .ai-recommend-skeleton {',
            '    flex-direction: column;',
            '  }',
            '}'
        ].join('\n');

        var style = document.createElement('style');
        style.textContent = css;
        document.head.appendChild(style);
    }

    // ===========================================
    // 共用工具函數
    // ===========================================

    // XSS 防護函數
    function sanitizeHTML(str) {
        var temp = document.createElement('div');
        temp.textContent = str;
        return temp.innerHTML;
    }

    // 顯示載入動畫
    function showLoadingAnimation(container) {
        container.innerHTML =
            '<div class="ai-recommend-header">' +
            '<div class="ai-recommend-icon">' +
            '<img src="/images/ai_logo.png" alt="AI" style="width: 40px; height: auto;">' +
            '</div>' +
            '<div class="ai-recommend-title">想知道更多？AI 一次說給你聽！</div>' +
            '</div>' +
            '<div class="ai-recommend-skeleton">' +
            '<div class="skeleton-item">' +
            '<div class="skeleton-line" style="width: 100%;"></div>' +
            '<div class="skeleton-line" style="width: 70%;"></div>' +
            '</div>' +
            '<div class="skeleton-item">' +
            '<div class="skeleton-line" style="width: 90%;"></div>' +
            '<div class="skeleton-line" style="width: 50%;"></div>' +
            '</div>' +
            '<div class="skeleton-item">' +
            '<div class="skeleton-line" style="width: 95%;"></div>' +
            '<div class="skeleton-line" style="width: 80%;"></div>' +
            '</div>' +
            '</div>';
    }

    // 更新頁面標題顯示
    function updatePageTitle(title) {
        // 安全地處理標題，防止XSS
        var safeTitle = sanitizeHTML(title);

        // 更新瀏覽器標題
        var titleElement = document.querySelector('title');
        if (titleElement) {
            titleElement.textContent = safeTitle + ' - AI文章';
        }

        // 更新頁面中的標題顯示容器
        var titleContainer = document.querySelector(config.titleSelector);
        if (titleContainer) {
            titleContainer.textContent = safeTitle;

        } else {

        }
    }

    // 顯示錯誤訊息
    function showError(container, message) {
        container.innerHTML = '<div style="color: #e74c3c; text-align: center; padding: 2rem;">錯誤：' + sanitizeHTML(message) + '</div>';
    }

    // 打字機效果函數（ES5 版本）
    function typeWriter(element, htmlContent, speed) {
        speed = speed || 20;

        return new Promise(function (resolve) {
            var tempDiv = document.createElement('div');
            tempDiv.innerHTML = htmlContent;
            var textContent = tempDiv.textContent || tempDiv.innerText || '';

            element.innerHTML = '';
            var i = 0;

            var timer = setInterval(function () {
                var currentText = textContent.substring(0, i + 1);
                element.textContent = currentText;
                i++;

                if (i >= textContent.length) {
                    clearInterval(timer);
                    if (htmlContent !== textContent) {
                        element.innerHTML = htmlContent;
                    }
                    resolve();
                }
            }, speed);
        });
    }

    // 模擬 Promise（針對舊瀏覽器）
    if (typeof Promise === 'undefined') {
        window.Promise = function (executor) {
            var self = this;
            self.state = 'pending';
            self.value = undefined;
            self.handlers = [];

            function resolve(result) {
                if (self.state === 'pending') {
                    self.state = 'fulfilled';
                    self.value = result;
                    self.handlers.forEach(handle);
                    self.handlers = null;
                }
            }

            function reject(error) {
                if (self.state === 'pending') {
                    self.state = 'rejected';
                    self.value = error;
                    self.handlers.forEach(handle);
                    self.handlers = null;
                }
            }

            function handle(handler) {
                if (self.state === 'pending') {
                    self.handlers.push(handler);
                } else {
                    if (self.state === 'fulfilled' && typeof handler.onFulfilled === 'function') {
                        handler.onFulfilled(self.value);
                    }
                    if (self.state === 'rejected' && typeof handler.onRejected === 'function') {
                        handler.onRejected(self.value);
                    }
                }
            }

            this.then = function (onFulfilled, onRejected) {
                return new Promise(function (resolve, reject) {
                    handle({
                        onFulfilled: function (result) {
                            try {
                                resolve(onFulfilled ? onFulfilled(result) : result);
                            } catch (ex) {
                                reject(ex);
                            }
                        },
                        onRejected: function (error) {
                            try {
                                resolve(onRejected ? onRejected(error) : error);
                            } catch (ex) {
                                reject(ex);
                            }
                        }
                    });
                });
            };

            try {
                executor(resolve, reject);
            } catch (ex) {
                reject(ex);
            }
        };
    }

    // ===========================================
    // 第一頁功能：相關主題推薦
    // ===========================================

    // 提取文章標題
    function extractArticleTitle() {
        try {
            var titleElement = document.querySelector(config.firstPageTitleSelector);
            if (titleElement) {

                return titleElement.textContent.trim();
            } else {

                return '';
            }

        } catch (error) {
            return '';
        }
    }

    // 提取文章內文
    function extractArticleContent() {
        try {
            var contentContainer = document.querySelector('div.news_content > div.articleBody.clearfix') ||
                document.querySelector('.article-content') ||
                document.querySelector('article') ||
                document.querySelector('main');
            if (!contentContainer) return '';

            var paragraphs = contentContainer.querySelectorAll('p:not([id]):not([class]):not([name])');

            var content = '';
            for (var i = 0; i < paragraphs.length; i++) {
                var text = paragraphs[i].textContent.trim();
                if (text) {
                    content += text + ' ';
                }
            }

            return content.trim();
        } catch (error) {

            return '';
        }
    }

    // 模擬 AI API 回應（第一頁）
    function getMockTopicsResponse() {
        return {
            reply: '1. AI醫療診斷技術的最新突破與臨床應用\n' +
                '2. 機器學習在預防醫學中的創新應用\n' +
                '3. 智慧醫療設備如何改變患者體驗\n' +
                '4. 人工智慧輔助藥物研發的前景分析\n' +
                '5. 遠距醫療與AI技術的完美結合',
            error: null
        };
    }

    // 呼叫 AI API 獲取相關主題（type 1）
    function callTopicsAPI(title) {
        return new Promise(function (resolve, reject) {
            // 如果啟用模擬模式
            if (config.enableMockMode) {

                setTimeout(function () {
                    resolve(getMockTopicsResponse());
                }, config.mockDelay);
                return;
            }



            // 嘗試真實 API 呼叫
            var xhr = new XMLHttpRequest();
            xhr.open('POST', config.apiEndpoint, true);
            xhr.setRequestHeader('Content-Type', 'application/json');

            xhr.onreadystatechange = function () {
                if (xhr.readyState === 4) {
                    if (xhr.status === 200) {
                        try {
                            var data = JSON.parse(xhr.responseText);

                            resolve(data);
                        } catch (e) {

                            resolve({ error: 'API Error: Parse failed' });
                        }
                    } else {
                        resolve({ error: 'API Error: ' + xhr.status });
                    }
                }
            };

            xhr.onerror = function () {

                resolve({ error: 'API Error: Network failed' });
            };

            try {
                // 改為傳送 JSON 物件: { url: "...", title: "..." }
                var payload = {
                    url: window.location.href,
                    title: title
                };

                xhr.send(JSON.stringify(payload));
            } catch (e) {

                resolve({ error: 'API Error: Request setup failed' });
            }
        });
    }

    // 顯示 AI 智慧推薦模組
    function displayTopicsModule(responseWrapper, container) {
        // 因應 Cloud Run 回傳格式調整：responseWrapper 為 { data: { content: [{title, url}, ...] } }
        // 或是直接為陣列 (如果 resolve 直接傳回陣列)

        var topics = [];
        // 處理不同的回應結構
        if (Array.isArray(responseWrapper)) {
            topics = responseWrapper;
        } else if (responseWrapper && responseWrapper.data && Array.isArray(responseWrapper.data.content)) {
            topics = responseWrapper.data.content;
        } else if (responseWrapper && responseWrapper.data && typeof responseWrapper.data.content === 'string') {
            // 相容舊的字串格式 (模擬模式)
            var reply = responseWrapper.data.content;
            reply = reply.replace(/^[^\n]*?:\s*\n/, '');
            var lines = reply.split('\n').filter(function (line) { return line.trim(); });
            for (var k = 0; k < lines.length; k++) {
                var clean = lines[k].replace(/^\d+\.\s*/, '').replace(/[、。]/g, '').trim();
                if (clean) topics.push({ title: clean, url: config.secondPageUrl + '?title=' + encodeURIComponent(clean) });
            }
        }

        // 舊版 API (測試用)
        // apiEndpoint: 'https://dev88.newtalk.tw/api/Other/AiTopic',
        // 正式環境 Cloud Run API
        // 第二頁面 URL
        // secondPageUrl: 'https://dev-ai.newtalk.tw/article/',
        // 取前 3 筆
        topics = topics.slice(0, 3);

        // 如果沒有內容，隱藏模組
        if (topics.length === 0) {
            container.innerHTML = '';
            container.style.display = 'none';
            return;
        }

        // 確保容器顯示（如果之前被隱藏）
        container.style.display = 'block';

        // 構建推薦列表 HTML
        var listHtml = '<div class="ai-recommend-list">';

        for (var i = 0; i < topics.length; i++) {
            var item = topics[i];
            // 處理標題
            var titleText = item.title || item.ArticleTitle; // 相容不同命名
            var urlText = item.url || item.ArticleUrl;       // 相容不同命名

            if (titleText && urlText) {
                var safeTitle = sanitizeHTML(titleText);

                listHtml +=
                    '<a href="' + urlText + '" target="_blank" class="ai-recommend-item" title="' + safeTitle + '">' +
                    '<span class="ai-recommend-text">' +
                    safeTitle +
                    '</span>' +
                    '</a>';
            }
        }

        listHtml += '</div>';

        // 檢查容器內是否有 Skeleton，如果有則僅替換 Skeleton，保留 Header 以避免閃爍
        var skeleton = container.querySelector('.ai-recommend-skeleton');
        if (skeleton) {
            // 創建臨時元素以轉換字串為 DOM
            var temp = document.createElement('div');
            temp.innerHTML = listHtml;
            var newList = temp.firstElementChild;

            // 替換 Skeleton
            if (skeleton.parentNode) {
                skeleton.parentNode.replaceChild(newList, skeleton);
            } else {
                // 防禦性代碼，理論上不應發生
                container.innerHTML += listHtml;
            }
        } else {
            // Fallback: 如果沒有找到 Skeleton (例如容器被清空或是初次渲染無狀態)，則重繪整個容器
            var fullHtml =
                '<div class="ai-recommend-header">' +
                '<div class="ai-recommend-icon">' +
                '<img src="/images/ai_logo.png" alt="AI" style="width: 40px; height: auto;">' +
                '</div>' +
                '<div class="ai-recommend-title">想知道更多？AI 一次說給你聽！</div>' +
                '</div>' +
                listHtml;

            container.innerHTML = fullHtml;
        }
    }

    // ===========================================
    // 第一頁功能：相關主題推薦
    // 容器 ID: #popin_recommend_ai
    // 功能：分析頁面內容，生成 3 個相關主題連結
    // ===========================================
    function executePageOneFunction() {
        var container = document.getElementById('popin_recommend_ai');
        if (!container) return;

        showLoadingAnimation(container);

        var title = extractArticleTitle();

        if (!title) {
            showError(container, '無法提取文章標題，請確認標題選擇器是否正確');
            return;
        }



        callTopicsAPI(title)
            .then(function (data) {

                if (data.error) {
                    // 發生錯誤時隱藏模組
                    container.innerHTML = '';
                    container.style.display = 'none';
                } else {
                    displayTopicsModule(data, container);
                }
            })
            .then(null, function (error) {
                // 發生錯誤時隱藏模組
                container.innerHTML = '';
                container.style.display = 'none';
            });
    }

    // ===========================================
    // 第二頁功能：文章生成
    // ===========================================

    // 從 URL 獲取參數（ES5 兼容版本）
    function getUrlParameter(name) {
        var urlParams = window.location.search.substring(1);
        var params = urlParams.split('&');

        for (var i = 0; i < params.length; i++) {
            var param = params[i].split('=');
            if (param[0] === name) {
                return decodeURIComponent(param[1]);
            }
        }
        return null;
    }

    // 模擬 AI API 回應（第二頁）
    function getMockArticleResponse(title) {
        return {
            reply: '在當今快速發展的科技時代，「' + title + '」已成為一個備受關注的重要議題。這個主題不僅影響著我們的日常生活，更對整個社會產生深遠的影響。\n\n' +
                '從技術層面來看，相關領域的創新正以前所未有的速度推進。專家指出，這些技術突破將為人類帶來更多便利，同時也創造了無數的發展機會。根據最新的研究數據顯示，相關產業的市場規模預計在未來五年內將實現大幅增長。\n\n' +
                '在實際應用方面，我們已經可以看到許多成功的案例。這些應用不僅提升了效率，更重要的是改善了用戶體驗。許多企業開始投入大量資源進行相關研發，希望能在這個競爭激烈的市場中占據一席之地。\n\n' +
                '然而，任何新技術的發展都伴隨著挑戰。如何確保技術的安全性、可靠性以及社會責任，成為了業界和學術界共同關注的焦點。專家建議，在推進技術發展的同時，必須建立完善的監管機制和倫理框架。\n\n' +
                '展望未來，這個領域將繼續呈現快速發展的趨勢。隨著更多創新技術的出現和應用場景的擴展，我們有理由相信，這將為社會帶來更多正面的影響和價值。',
            error: null
        };
    }

    // 呼叫 AI API 生成文章（type 2）
    function callArticleAPI(title) {

        return new Promise(function (resolve, reject) {
            // 如果啟用模擬模式
            if (config.enableMockMode) {

                setTimeout(function () {
                    resolve(getMockArticleResponse(title));
                }, config.mockDelay);
                return;
            }



            // 嘗試真實 API 呼叫
            var xhr = new XMLHttpRequest();
            xhr.open('POST', config.apiEndpoint, true);
            xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded');

            xhr.onreadystatechange = function () {
                if (xhr.readyState === 4) {
                    if (xhr.status === 200) {
                        try {
                            var data = JSON.parse(xhr.responseText);

                            resolve(data);
                        } catch (e) {

                            resolve(getMockArticleResponse(title));
                        }
                    } else {

                        resolve(getMockArticleResponse(title));
                    }
                }
            };

            xhr.onerror = function () {

                resolve(getMockArticleResponse(title));
            };

            try {
                var requestBody = 'type=2&message=' + encodeURIComponent(title);

                xhr.send(requestBody);
            } catch (e) {

                resolve(getMockArticleResponse(title));
            }
        });
    }

    // 顯示文章內容與打字機效果（ES5 版本）
    function displayArticleWithTypewriter(content, container) {
        return new Promise(function (resolve) {
            // 先清空容器並添加樣式類
            container.innerHTML = '';
            container.className += ' typewriter-container';

            // 將內容按段落分割
            var paragraphs = content.split('\n\n').filter(function (p) { return p.trim(); });
            var currentIndex = 0;

            function displayNextParagraph() {
                if (currentIndex >= paragraphs.length) {
                    resolve();
                    return;
                }

                var paragraph = paragraphs[currentIndex].trim();
                if (!paragraph) {
                    currentIndex++;
                    displayNextParagraph();
                    return;
                }

                // 創建段落元素
                var p = document.createElement('p');
                p.style.minHeight = '1.2em';
                container.appendChild(p);

                // 使用打字機效果顯示段落
                typeWriter(p, paragraph, 15)
                    .then(function () {
                        currentIndex++;
                        // 段落間延遲
                        setTimeout(function () {
                            displayNextParagraph();
                        }, 200);
                    });
            }

            displayNextParagraph();
        });
    }

    // ===========================================
    // 第二頁功能：AI 文章生成
    // 容器 ID: #popin_recommend_ai_res
    // 功能：根據 URL 參數中的標題生成 800 字文章
    // ===========================================
    function executePageTwoFunction() {
        var container = document.getElementById('popin_recommend_ai_res');
        if (!container) return;

        // 從 URL 獲取標題參數
        var title = getUrlParameter('title');

        if (!title) {
            showError(container, '缺少標題參數');
            return;
        }

        // 更新頁面標題顯示
        updatePageTitle(title);

        showLoadingAnimation(container);



        callArticleAPI(title)
            .then(function (data) {
                if (data.error) {
                    showError(container, data.error);
                } else {
                    return displayArticleWithTypewriter(data.reply, container);
                }
            })
            .then(null, function (error) {
                showError(container, '處理錯誤：' + error.message);
            });
    }

    // ===========================================
    // 主要初始化函數
    // ===========================================

    function initializeModule() {
        // 注入 CSS 樣式
        injectCSS();

        // ===========================================
        // 自動偵測頁面類型並執行對應功能
        // ===========================================

        // 檢查第一頁容器：相關主題推薦
        // 媒體商需在第一頁放置：<div id="popin_recommend_ai"></div>
        var pageOneContainer = document.getElementById('popin_recommend_ai');
        if (pageOneContainer) {

            executePageOneFunction();
        }

        // 檢查第二頁容器：AI 文章生成
        // 媒體商需在第二頁放置：<div id="popin_recommend_ai_res"></div>
        var pageTwoContainer = document.getElementById('popin_recommend_ai_res');
        if (pageTwoContainer) {

            executePageTwoFunction();
        }

    }

    // ===========================================
    // Log 記錄功能 (New)
    // ===========================================

    // 取得 Cookie
    function getCookie(name) {
        var value = "; " + document.cookie;
        var parts = value.split("; " + name + "=");
        if (parts.length === 2) return parts.pop().split(";").shift();
        return "";
    }

    // 發送 Log 到後端
    function sendLog(eventType, eventData) {
        // 基本資料
        var payload = {
            log_mode: true,
            event_type: eventType,
            timestamp: new Date().toISOString(), // 雖然 BigQuery 會自動產生，但前端傳送可做參考
            media_url: window.location.href,
            media_title: document.title,
            user_agent: navigator.userAgent,
            pacid: getCookie("pacid") || "", // 取得 pacid cookie
            viewport: window.innerWidth + 'x' + window.innerHeight,
            device_type: window.innerWidth < 768 ? 'mobile' : 'desktop'
        };

        // 合併特定事件資料 (ai_title, ai_url, ad_position 等)
        for (var key in eventData) {
            if (eventData.hasOwnProperty(key)) {
                payload[key] = eventData[key];
            }
        }



        // 使用 fetch + keepalive (最推薦的現代做法，CORS 處理較穩健)
        if (window.fetch) {
            fetch(config.apiEndpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload),
                keepalive: true, // 確保頁面關閉時請求仍會發送
                mode: 'cors'
            }).then(null, function (error) {

            });
        }
        // 降級：Navigator.sendBeacon
        else if (navigator.sendBeacon) {
            var blob = new Blob([JSON.stringify(payload)], { type: 'application/json' });
            navigator.sendBeacon(config.apiEndpoint, blob);
        }
        // 最後降級：XMLHttpRequest
        else {
            var xhr = new XMLHttpRequest();
            xhr.open('POST', config.apiEndpoint, true);
            xhr.setRequestHeader('Content-Type', 'application/json');
            xhr.send(JSON.stringify(payload));
        }
    }

    // 綁定 Log 事件
    function bindLogEvents(container, items) {
        // 設定 IntersectionObserver 監聽 Impression
        if ('IntersectionObserver' in window) {
            var observer = new IntersectionObserver(function (entries) {
                entries.forEach(function (entry) {
                    if (entry.isIntersecting) {
                        var item = entry.target;
                        // 避免重複計數
                        if (!item.dataset.logged) {
                            item.dataset.logged = 'true';
                            var index = Array.prototype.indexOf.call(items, item);

                            sendLog('imp', {
                                ai_title: item.getAttribute('title') || item.querySelector('.ai-recommend-text').textContent,
                                ai_url: item.getAttribute('href'),
                                ad_position: index + 1
                            });
                            observer.unobserve(item);
                        }
                    }
                });
            }, { threshold: 0.5 }); // 50% 可見視為曝光

            for (var i = 0; i < items.length; i++) {
                observer.observe(items[i]);
            }
        }

        // 綁定 Click 事件
        for (var j = 0; j < items.length; j++) {
            (function (index) {
                var item = items[index];
                item.addEventListener('click', function () {
                    sendLog('click', {
                        ai_title: item.getAttribute('title') || item.querySelector('.ai-recommend-text').textContent,
                        ai_url: item.getAttribute('href'),
                        ad_position: index + 1
                    });
                });
            })(j);
        }
    }

    // 修改 displayTopicsModule 以綁定事件
    var originalDisplayTopicsModule = displayTopicsModule;
    displayTopicsModule = function (responseWrapper, container) {
        // 呼叫原始函數渲染畫面
        originalDisplayTopicsModule(responseWrapper, container);

        // 綁定事件
        setTimeout(function () {
            var items = container.querySelectorAll('.ai-recommend-item');
            if (items.length > 0) {
                bindLogEvents(container, items);
            }
        }, 100);
    };

    // 啟動模組
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initializeModule);
    } else {
        initializeModule();
    }

})();