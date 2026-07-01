/**
 * Popin AI Module (v1.5)
 *
 * 相較 v1.4 的變更：
 * 1. 移除整套「第二頁 AI 文章生成」功能（第二頁已由 newtalk 以 Nuxt 自控，
 *    不再載入本模組）：typeWriter / callArticleAPI / getMockArticleResponse /
 *    displayArticleWithTypewriter / executePageTwoFunction / getUrlParameter /
 *    updatePageTitle 全數移除。
 * 2. 第一頁三張推薦卡片新增「輪播循環打字機」效果：進入可視視窗才跑、
 *    捲離暫停、1→2→3 無限循環。
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
        // 第二頁 URL（僅供模擬字串格式的連結 fallback 使用）
        secondPageUrl: 'test_page2_1104.html',
        // 第一頁標題提取選擇器 (請媒體商調整為實際的標題選擇器)
        firstPageTitleSelector: 'div.news_info > div.title > p.name',
        // 模擬延遲時間（毫秒）
        mockDelay: 2000,
        // 除錯模式
        debugMode: true
    };

    // ===========================================
    // 打字機輪播效果參數（第一頁三張推薦卡片）
    // ===========================================
    var TW_SPEED = 55;        // 每個字的間隔（毫秒）
    var TW_HOLD = 900;        // 一張打完、換下一張前的停頓（毫秒）
    var TW_START_DELAY = 300; // 進入視窗後、開始打字前的延遲（毫秒）

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
            '}',
            '',
            '/* 打字機游標（只在正在打字的那段顯示並閃爍）*/',
            '.ai-recommend-text.is-typing::after {',
            '  content: \'\';',
            '  display: inline-block;',
            '  width: 2px;',
            '  height: 1em;',
            '  margin-left: 2px;',
            '  background: #006A7C;',
            '  vertical-align: text-bottom;',
            '  animation: tw-blink 0.8s step-end infinite;',
            '}',
            '',
            '@keyframes tw-blink { 50% { opacity: 0; } }'
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

    // 顯示錯誤訊息
    function showError(container, message) {
        container.innerHTML = '<div style="color: #e74c3c; text-align: center; padding: 2rem;">錯誤：' + sanitizeHTML(message) + '</div>';
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
    // 打字機輪播效果（第一頁三張推薦卡片）
    // 進入可視視窗才跑、捲離暫停、1→2→3 無限循環。
    //
    // 與 log 埋點的相容性：
    //   完整標題會先存進每個 span 的 data-text 屬性，打字過程僅改動 textContent；
    //   log 上報（bindLogEvents）優先讀 <a> 的 title 屬性，故即使曝光/點擊剛好
    //   發生在打字打到一半，上報的標題仍是完整的，不會抓到半截字。
    // ===========================================
    function initTypewriter(widget) {
        var els = Array.prototype.slice.call(widget.querySelectorAll('.ai-recommend-text'));
        if (els.length === 0) return;

        // 記住每張的完整標題（render 當下 textContent 即為完整標題）
        els.forEach(function (el) {
            el.setAttribute('data-text', el.textContent);
        });

        var timers = [];
        var runId = 0;   // 每次啟動 +1；用來取消上一輪（捲離畫面時）

        function clearTimers() {
            for (var i = 0; i < timers.length; i++) {
                clearTimeout(timers[i]);
            }
            timers = [];
        }

        // 全部顯示完整標題、移除游標
        function fillAll() {
            els.forEach(function (el) {
                el.textContent = el.getAttribute('data-text') || '';
                el.classList.remove('is-typing');
            });
        }

        // 對單一張做打字機效果，完成後 resolve
        function typeOne(el, myRun) {
            return new Promise(function (resolve) {
                var full = el.getAttribute('data-text') || '';
                el.textContent = '';
                el.classList.add('is-typing');
                var i = 0;
                (function step() {
                    if (myRun !== runId) { resolve(); return; } // 已被取消
                    if (i <= full.length) {
                        el.textContent = full.substring(0, i);
                        i++;
                        timers.push(setTimeout(step, TW_SPEED));
                    } else {
                        el.classList.remove('is-typing');
                        resolve();
                    }
                })();
            });
        }

        // 啟動循環：1→2→3→1…，一次只有一張打字，其餘顯示完整
        function startLoop() {
            clearTimers();
            runId++;
            var myRun = runId;

            var idx = 0;
            function nextCard() {
                if (myRun !== runId) return;
                // 其它張顯示完整標題（正在打字的那張交給 typeOne 清空重打）
                els.forEach(function (el, i) {
                    if (i !== idx) {
                        el.textContent = el.getAttribute('data-text') || '';
                        el.classList.remove('is-typing');
                    }
                });
                typeOne(els[idx], myRun).then(function () {
                    if (myRun !== runId) return;
                    idx = (idx + 1) % els.length;        // 循環到下一張
                    timers.push(setTimeout(nextCard, TW_HOLD));
                });
            }
            timers.push(setTimeout(nextCard, TW_START_DELAY));
        }

        // 停止循環（捲離畫面）：取消計時器、回到全部完整顯示
        function stopLoop() {
            runId++;          // 讓進行中的 step / Promise 失效
            clearTimers();
            fillAll();
        }

        // 初始：先讓三張都正常顯示完整標題
        fillAll();

        // ===== 進入可視視窗才跑、捲離就暫停（IntersectionObserver）=====
        if ('IntersectionObserver' in window) {
            var io = new IntersectionObserver(function (entries) {
                entries.forEach(function (entry) {
                    if (entry.isIntersecting) startLoop();  // 露出 35% → 開始循環
                    else stopLoop();                         // 捲離 → 暫停
                });
            }, { threshold: 0.35 });
            io.observe(widget);
        } else {
            startLoop(); // 不支援 IntersectionObserver 時直接跑
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
    // 主要初始化函數
    // ===========================================

    function initializeModule() {
        // 注入 CSS 樣式
        injectCSS();

        // ===========================================
        // 第一頁容器：相關主題推薦
        // 媒體商需在頁面放置：<div id="popin_recommend_ai"></div>
        // ===========================================
        var pageOneContainer = document.getElementById('popin_recommend_ai');
        if (pageOneContainer) {

            executePageOneFunction();
        }

    }

    // ===========================================
    // Log 記錄功能
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

    // 修改 displayTopicsModule 以綁定事件並啟動打字機
    var originalDisplayTopicsModule = displayTopicsModule;
    displayTopicsModule = function (responseWrapper, container) {
        // 呼叫原始函數渲染畫面
        originalDisplayTopicsModule(responseWrapper, container);

        // 綁定事件 + 啟動打字機
        setTimeout(function () {
            var items = container.querySelectorAll('.ai-recommend-item');
            if (items.length > 0) {
                bindLogEvents(container, items);
            }
            // 啟動打字機輪播（進可視範圍才跑、捲離暫停、無限循環）
            initTypewriter(container);
        }, 100);
    };

    // 啟動模組
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initializeModule);
    } else {
        initializeModule();
    }

})();
