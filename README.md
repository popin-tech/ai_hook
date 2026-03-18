# Popin AI Module - 智慧推薦模組

整合了第一頁相關主題推薦和第二頁文章生成功能的 JavaScript 模組。

## 功能特色

- 🎯 **智慧偵測**：自動偵測頁面容器並執行對應功能
- 🔄 **雙頁支援**：支援第一頁主題推薦和第二頁文章生成
- 🎨 **完整樣式**：內建所有必要的 CSS 樣式
- 🔒 **安全防護**：包含 XSS 防護機制
- 📱 **響應式設計**：支援手機和桌面版本
- ⚡ **即時執行**：DOM 載入完成後自動執行

## 使用方法

### 外部引入方式

```html
<!-- 在 HTML 頁面中引入 -->
<script src="path/to/popin_ai_module.js"></script>
```

### 頁面容器設定

#### 第一頁（相關主題推薦）
在需要顯示 AI 主題推薦的頁面中放置：
```html
<div id="popin_recommend_ai"></div>
```

#### 第二頁（文章生成）
在需要顯示 AI 生成文章的頁面中放置：
```html
<div id="popin_recommend_ai_res"></div>
```

## 工作流程

### 第一頁功能
1. **偵測容器**：尋找 `#popin_recommend_ai`
2. **提取內容**：自動提取頁面標題和文章內容
3. **AI 分析**：呼叫 AI API 生成相關主題
4. **顯示結果**：以智慧閱讀模組形式顯示 3 個相關主題

### 第二頁功能
1. **偵測容器**：尋找 `#popin_recommend_ai_res`
2. **取得參數**：從 URL 的 `title` 參數取得主題
3. **生成文章**：呼叫 AI API 生成 800 字文章
4. **打字機效果**：逐段落顯示文章內容

## API 需求

模組需要後端提供 `chat_api.php` 端點：

```php
// POST /chat_api.php
// Content-Type: application/json
// Body: {"message": "AI prompt here"}
// Response: {"reply": "AI response", "error": null}
```

## 技術特色

### 自動偵測機制
```javascript
// DOM Ready 後自動執行
domReady(() => {
    // 檢查第一頁容器
    if (document.getElementById('popin_recommend_ai')) {
        executePageOneFunction();
    }
    
    // 檢查第二頁容器
    if (document.getElementById('popin_recommend_ai_res')) {
        executePageTwoFunction();
    }
});
```

### 安全防護
- XSS 防護：所有用戶輸入都經過 `sanitizeHTML()` 處理
- URL 編碼：所有 URL 參數都經過適當編碼
- 錯誤處理：完整的錯誤捕獲和用戶友善提示

### 響應式設計
- 桌面版：3 欄橫向排列的主題列表
- 平板版：適中的間距和字體
- 手機版：單欄垂直排列，優化觸控體驗

## 自訂選項

### CSS 樣式自訂
所有樣式都包含在 JS 檔案中，可以通過修改 `injectCSS()` 函數來自訂：

```javascript
function injectCSS() {
    const css = `
        /* 在這裡修改樣式 */
        .ai-reading-module {
            /* 自訂主容器樣式 */
        }
    `;
    // ...
}
```

### API 端點自訂
修改 API 呼叫函數中的端點：

```javascript
// 第一頁 API
const response = await fetch('your-custom-api.php', {
    // ...
});

// 第二頁 API  
const response = await fetch('your-custom-api.php', {
    // ...
});
```

## 瀏覽器支援

- Chrome 60+
- Firefox 55+
- Safari 12+
- Edge 79+

## 檔案結構

```
integrated_ai_module/
├── popin_ai_module.js    # 主要模組檔案
└── README.md             # 使用說明文件
```

## 開發者 API

模組對外暴露以下 API：

```javascript
// 重新初始化模組
window.PopinAI.reinitialize();

// 提取頁面標題
const title = window.PopinAI.extractTitle();

// 提取頁面內容
const content = window.PopinAI.extractContent();

// 查看版本
console.log(window.PopinAI.version); // "1.0.0"
```

## 故障排除

### 常見問題

1. **模組沒有執行**
   - 確認頁面有正確的容器 div
   - 檢查 console 是否有錯誤訊息
   - 確認 chat_api.php 端點可以正常存取

2. **樣式沒有套用**
   - 確認沒有其他 CSS 覆蓋模組樣式
   - 檢查 CSP (Content Security Policy) 設定

3. **API 呼叫失敗**
   - 檢查網路連線
   - 確認後端 API 端點正常運作
   - 查看 browser developer tools 的 Network 標籤

### 除錯模式

在瀏覽器 console 中可以看到模組的執行日誌：

```
偵測到第一頁容器，執行相關主題推薦功能
第一頁 - 提取到的標題: [標題內容]
第一頁 - 提取到的內文長度: [字數]
```

## 更新日誌

### v1.0.0
- 整合第一頁和第二頁功能
- 自動容器偵測機制
- 完整的響應式設計
- 內建安全防護機制