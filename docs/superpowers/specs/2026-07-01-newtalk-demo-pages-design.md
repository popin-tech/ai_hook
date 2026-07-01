# Newtalk AI 廣告模組 客戶 Demo 頁 設計文件

**日期**：2026-07-01
**目的**：用現有 `ai-ad-generate` 服務 + `newtalk_a.json` 設定，做出「像真的一樣」的模擬頁給客戶媒體看上線後的樣子，部署到 GitHub Pages 產出 public url。

---

## 1. 已定案決策

| 決策點 | 選擇 |
|--------|------|
| Demo 完整度 | **完整可點擊**：3 個第一頁 + 每篇 3 篇第二頁 AI 文章 = 12 頁 |
| AI 內容來源 | **預先凍結真實產出**（用 `test_mode` 把 newtalk_a 真實產出寫死進靜態頁） |
| 第二頁內文呈現 | **逐段打字機動畫**（沿用舊版第二頁效果） |
| 部署位置 | **`gh-pages` 分支**（與 main 隔離，正式程式碼不混入 demo 檔） |
| 入口頁 | **要做**（index 導覽列出 3 篇 demo） |

---

## 2. 三篇來源文章

| ID | 標題 | 分類 | 原始 url |
|----|------|------|----------|
| 1044556 | 搶進大馬綠色旅遊市場「高雄農村旅遊」成海外推介新亮點 | 生活 | newtalk.tw/news/view/2026-07-01/1044556 |
| 1044472 | 劉亞仁涉毒停工3年「爆投靠GD公司復出」？傳天價簽約金「飆破50億韓元」 | 娛樂 | newtalk.tw/news/view/2026-07-01/1044472 |
| 1043615 | 懶人包》果粉哀號！蘋果宣布iPad、Mac全面調漲 最新售價一次看 | 科技 | newtalk.tw/news/view/2026-06-26/1043615 |

三篇真實內文已透過 WebFetch 完整抽取，主題/分類/作者/發布時間皆保留原樣。

---

## 3. 頁面結構

```
(gh-pages 分支根目錄)          （檔案直接放分支根，不套 docs/ 子層）
├── index.html                 入口導覽頁：列 3 篇 demo 卡片
├── article/
│   ├── 1044556.html           第一頁：高雄農遊
│   ├── 1044472.html           第一頁：劉亞仁
│   └── 1043615.html           第一頁：蘋果漲價
├── ai/
│   ├── 1044556-1.html ~ -3.html   第二頁：高雄農遊 3 篇 AI 延伸閱讀
│   ├── 1044472-1.html ~ -3.html   第二頁：劉亞仁 3 篇
│   └── 1043615-1.html ~ -3.html   第二頁：蘋果 3 篇
└── assets/
    ├── site.css               共用樣式（header / 文章版型 / 廣告色塊 / widget）
    ├── typewriter-loop.js      第一頁 AI 推薦 widget 輪播循環打字機
    └── typewriter-article.js   第二頁文章逐段打字機
```

---

## 4. 第一頁設計（模擬新頭殼文章頁）

- **版型基礎**：沿用專案既有的 `demo_typewriter.html`（已把 newtalk header/logo/雙欄版型/側欄焦點評論仿得很像），抽成共用 `site.css` + 各篇套入真實內容。
- **內容**：真實標題、作者、發布時間、分類麵包屑、逐段真實內文、真實示意圖（沿用 newtalk 圖床 url）。
- **AI 推薦 widget**（`#popin_recommend_ai`）：內文中段插入，3 張卡片標題為 newtalk_a 真實產出的吸睛標題，**輪播循環打字機**（進可視視窗才跑、捲離暫停、1→2→3 無限循環，即 v1.5 效果的凍結資料版）。每張卡片連到對應第二頁 `ai/{id}-{n}.html`。
- **廣告色塊**（動態版位以色塊 + 文字標示）：
  - header 下橫幅（970×90）
  - 內文中段矩形
  - 右側欄 300×250
  - 文末橫幅

## 5. 第二頁設計（AI 生成文章頁）

- 同款 newtalk header / 廣告色塊。
- 標題 + 內文為 newtalk_a 真實產出（每篇 600–700 字，含首行縮排與分段空行）。
- 內文用**逐段打字機動畫**（沿用舊版 `displayArticleWithTypewriter` 效果：一段打完再打下一段）。
- 頁尾標註「本內容由 AI 依 newtalk_a 設定真實產出」。

## 6. 資料來源與凍結流程

對三篇各呼叫一次 `test_mode`，把真實產出寫死進靜態頁：

```
POST https://ai-ad-439393162392.asia-east1.run.app
{ "test_mode": true, "provider": "gemini", "config_name": "newtalk_a",
  "count": 3, "url": "<原文url>", "title": "<原文標題>" }
→ 回 [{ "ArticleTitle": "...", "ArticleContent": "..." } × 3]
```

- 第一篇（高雄農遊）已實測成功產出 3 組。
- 第二、三篇待跑。
- 每篇的 3 個 `ArticleTitle` → 第一頁推薦卡片標題；對應 `ArticleContent` → 該第二頁內文。

## 7. 部署

- 建立 `gh-pages` 分支，檔案直接放分支根目錄（index.html / article/ / ai/ / assets/）。
- 開啟 GitHub Pages：source = `gh-pages` 分支根目錄。優先用 `gh api` 開；若組織權限受限，提供 repo Settings → Pages 手動步驟。
- Public URL 形式：`https://popin-tech.github.io/ai_hook/`（入口頁），子頁依上述路徑。

## 8. 待辦步驟概覽

1. 跑第二、三篇 `test_mode`，收齊 9 組真實 AI 產出。
2. 抽 `demo_typewriter.html` 版型為 `site.css` + 兩支打字機 JS。
3. 產出 3 個第一頁、9 個第二頁、1 個入口頁（共 13 檔）。
4. 建 `gh-pages` 分支、放 `docs/`、push。
5. 開啟 GitHub Pages、驗證 public url 可正常瀏覽與點擊。

## 9. 風險與注意

- **內容凍結一致性**：demo 用凍結產出，客戶每次看內容固定；頁尾註明真實產出來源以免被誤會是假資料。
- **圖片相依**：示意圖與 logo 沿用 newtalk 線上圖床 url，若對方圖床擋外連或圖失效，改用色塊 placeholder。
- **Pages 權限**：org repo 開 Pages 可能需要管理員權限，最壞情況需請使用者手動開一次。
- **範圍限制**：這是一次性展示用靜態 demo，不接即時 API、不含正式上線的 polling/log 行為（那些在 v1.5 正式模組已具備，非本 demo 目標）。
