/* 第二頁 AI 文章：逐段打字機（進入可視範圍才開始，一次性、不循環）
   每段文字預存於 data-text，進場後一段打完再打下一段。 */
(function () {
    var SPEED = 12;        // 內文較長，速度快一點
    var GAP = 220;         // 段落之間的停頓

    var container = document.querySelector('.ai-article-body');
    if (!container) return;
    var ps = Array.prototype.slice.call(container.querySelectorAll('p'));
    if (ps.length === 0) return;

    // 預存完整段落文字並清空
    ps.forEach(function (p) { p.setAttribute('data-text', p.textContent); p.textContent = ''; });

    var started = false;
    function typeP(p, done) {
        var full = p.getAttribute('data-text') || '';
        var i = 0;
        p.classList.add('is-typing');
        (function step() {
            if (i <= full.length) { p.textContent = full.substring(0, i); i++; setTimeout(step, SPEED); }
            else { p.classList.remove('is-typing'); done && done(); }
        })();
    }
    function run() {
        if (started) return; started = true;
        var idx = 0;
        function next() {
            if (idx >= ps.length) return;
            typeP(ps[idx], function () { idx++; setTimeout(next, GAP); });
        }
        next();
    }

    if ('IntersectionObserver' in window) {
        var io = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) { if (entry.isIntersecting) { run(); io.disconnect(); } });
        }, { threshold: 0.1 });
        io.observe(container);
    } else {
        run();
    }
})();
