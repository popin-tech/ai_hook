/* 第一頁 AI 推薦 widget：輪播循環打字機（靜態凍結資料版）
   進入可視視窗才跑、捲離暫停、1→2→3 無限循環。
   完整標題存於 data-text，log 相容性同正式模組（此 demo 不送 log）。 */
(function () {
    var SPEED = 55;        // 每個字的間隔（毫秒）
    var HOLD = 900;        // 一張打完、換下一張前的停頓
    var START_DELAY = 300; // 進入視窗後、開始打字前的延遲

    var widget = document.getElementById('popin_recommend_ai');
    var els = widget ? Array.prototype.slice.call(widget.querySelectorAll('.ai-recommend-text')) : [];
    var timers = [];
    var runId = 0;

    function clearTimers() { for (var i = 0; i < timers.length; i++) clearTimeout(timers[i]); timers = []; }

    function fillAll() {
        els.forEach(function (el) {
            el.textContent = el.getAttribute('data-text') || '';
            el.classList.remove('is-typing');
        });
    }

    function typeOne(el, myRun) {
        return new Promise(function (resolve) {
            var full = el.getAttribute('data-text') || '';
            el.textContent = '';
            el.classList.add('is-typing');
            var i = 0;
            (function step() {
                if (myRun !== runId) { resolve(); return; }
                if (i <= full.length) { el.textContent = full.substring(0, i); i++; timers.push(setTimeout(step, SPEED)); }
                else { el.classList.remove('is-typing'); resolve(); }
            })();
        });
    }

    function startLoop() {
        clearTimers(); runId++;
        var myRun = runId;
        if (els.length === 0) return;
        var idx = 0;
        function nextCard() {
            if (myRun !== runId) return;
            els.forEach(function (el, i) {
                if (i !== idx) { el.textContent = el.getAttribute('data-text') || ''; el.classList.remove('is-typing'); }
            });
            typeOne(els[idx], myRun).then(function () {
                if (myRun !== runId) return;
                idx = (idx + 1) % els.length;
                timers.push(setTimeout(nextCard, HOLD));
            });
        }
        timers.push(setTimeout(nextCard, START_DELAY));
    }

    function stopLoop() { runId++; clearTimers(); fillAll(); }

    fillAll();

    if ('IntersectionObserver' in window && widget) {
        var io = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) startLoop(); else stopLoop();
            });
        }, { threshold: 0.35 });
        io.observe(widget);
    } else {
        startLoop();
    }
})();
