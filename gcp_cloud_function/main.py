import functions_framework
import requests
import json
import base64
import os
import re
import time
from urllib.parse import urlparse
from google.cloud import pubsub_v1
import datetime
import logging
import asyncio
import aiohttp
from dotenv import load_dotenv

# 載入 .env 檔案（本地開發用；GCP Cloud Run 直接使用控制台設定的環境變數）
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 配置 (從環境變數讀取)
# 運作方式：
#   - 本地開發：load_dotenv() 會從 .env 檔案讀取後注入環境變數
#   - GCP Cloud Run：.env 不存在，load_dotenv() 不做任何事，直接讀取 GCP 設定的環境變數
# ⚠️  GCP Cloud Run 請務必在「控制台 → 容器 → 變數與密鑰」設定以下環境變數

# NEWTALK_API_BASE 改為根據傳入 URL 動態決定
DEFAULT_API_BASE = os.environ.get("NEWTALK_API_BASE", "https://stage.newtalk.tw/aiArticle")
NEWTALK_API_TOKEN = os.environ.get("NEWTALK_API_TOKEN", "")
# Anthropic
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
# Gemini
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")  # 優先使用 API Key 模式
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3-flash-preview")
AI_PROVIDER = os.environ.get("AI_PROVIDER", "gemini")  # anthropic 或 gemini

# 啟動時驗證必要環境變數，若未設定則發出警告（便於 Cloud Run log 診斷）
_is_local = os.path.exists(os.path.join(os.path.dirname(__file__), ".env"))
_env_source = "本地 .env 檔案" if _is_local else "GCP Cloud Run 環境變數"
logger.info(f"[Config] 環境變數來源：{_env_source}")
logger.info(f"[Config] AI_PROVIDER={AI_PROVIDER}, GEMINI_MODEL={GEMINI_MODEL}, ANTHROPIC_MODEL={ANTHROPIC_MODEL}")

_required_vars = {
    "NEWTALK_API_TOKEN": NEWTALK_API_TOKEN,
    "GEMINI_API_KEY" if AI_PROVIDER == "gemini" else "ANTHROPIC_API_KEY":
        GEMINI_API_KEY if AI_PROVIDER == "gemini" else ANTHROPIC_API_KEY,
}
for _var_name, _var_val in _required_vars.items():
    if not _var_val:
        logger.warning(f"[Config] ⚠️  環境變數 {_var_name} 未設定！請檢查 .env（本地）或 Cloud Run 環境變數設定。")
    else:
        logger.info(f"[Config] ✅ {_var_name} 已載入")


# Pub/Sub Config
# TOPIC_ID = "popin-ai-ad-logs" 

def get_current_project_id():
    """嘗試獲取正確的 Project ID"""
    # 1. 優先讀取使用者自定義環境變數
    pid = os.environ.get("GCP_PROJECT_ID")
    if pid:
        logger.info(f"Using Project ID from GCP_PROJECT_ID env: {pid}")
        return pid
        
    # 2. 讀取 Cloud Run/Functions 預設環境變數
    pid = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if pid:
        logger.info(f"Using Project ID from GOOGLE_CLOUD_PROJECT env: {pid}")
        return pid

    # 3. 嘗試從 GCP Metadata Server 獲取 (最穩健的方式)
    try:
        url = "http://metadata.google.internal/computeMetadata/v1/project/project-id"
        headers = {"Metadata-Flavor": "Google"}
        response = requests.get(url, headers=headers, timeout=2)
        if response.status_code == 200:
            pid = response.text.strip()
            logger.info(f"Using Project ID from Metadata Server: {pid}")
            return pid
    except Exception as e:
        logger.warning(f"Failed to get Project ID from Metadata Server: {e}")
    
    return None

PROJECT_ID = get_current_project_id()
TOPIC_ID = "popin-ai-ad-logs" 

# Initialize Pub/Sub Publisher
publisher = None
publisher_init_error = None

if not PROJECT_ID:
    publisher_init_error = "Could not determine GCP Project ID. Please set GCP_PROJECT_ID env var."
    logger.error(publisher_init_error)
else:
    try:
        publisher = pubsub_v1.PublisherClient()
        topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)
        logger.info(f"Pub/Sub initialized with Topic: {topic_path}")
    except Exception as e:
        publisher_init_error = str(e)
        logger.error(f"Failed to initialize Pub/Sub publisher: {e}")

HEADERS = {
    "accept": "application/json",
    "Authorization": f"Bearer {NEWTALK_API_TOKEN}",
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def clean_url(url):
    logger.info(f"Entering clean_url with url={url}")
    """移除 URL 中的 query string"""
    return url.split('?')[0]

def get_api_base_from_url(url):
    """根據傳入的 URL 決定對應的 API base domain (使用 urlparse 確保準確性)"""
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        
        if not hostname:
            return DEFAULT_API_BASE
            
        if hostname == "dev88.newtalk.tw":
             return "https://dev88.newtalk.tw/aiArticle"
        elif hostname == "stage.newtalk.tw":
             return "https://stage.newtalk.tw/aiArticle"
        # 針對正式環境，可能有多種 hostname 變體
        elif hostname in ["newtalk.tw", "www.newtalk.tw", "api.newtalk.tw"]:
             return "https://api.newtalk.tw/aiArticle"
        else:
            # 其他子網域或無法識別的情況，使用預設值 (通常是 stage 或是環境變數設定值)
            return DEFAULT_API_BASE
            
    except Exception as e:
        logger.error(f"Error parsing URL {url}: {e}")
        return DEFAULT_API_BASE

async def get_popin_article(session, url, api_base):
    logger.info(f"Entering get_popin_article with url={url}, api_base={api_base}")
    """查詢 Newtalk DB 是否有文章資料"""
    api_url = f"{api_base}/GetPopinArticle"
    payload = {"url": url}

    # Debug: 印出完整的 HTTP request 資訊
    logger.info("=" * 50)
    logger.info("[DEBUG] HTTP Request Details:")
    logger.info(f"  Endpoint: {api_url}")
    logger.info(f"  Method: POST")
    logger.info(f"  Headers: {json.dumps(HEADERS, indent=4, ensure_ascii=False)}")
    logger.info(f"  Payload: {json.dumps(payload, indent=4, ensure_ascii=False)}")
    logger.info("=" * 50)

    try:
        async with session.post(api_url, headers=HEADERS, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as response:
            resp_text = await response.text()
            # Debug: 印出完整的 HTTP response 資訊
            logger.info("[DEBUG] HTTP Response Details:")
            logger.info(f"  Status Code: {response.status}")
            logger.info(f"  Response Headers: {dict(response.headers)}")
            logger.info(f"  Response Body: {resp_text}")
            logger.info("=" * 50)

            if response.status == 200:
                return json.loads(resp_text)
            else:
                logger.error(f"GetPopinArticle Failed: Status={response.status}, Response={resp_text}")
    except Exception as e:
        logger.error(f"Error calling GetPopinArticle: {e}")
    return None

async def insert_popin_article(session, original_url, ai_data, api_base):
    print(f"Entering insert_popin_article with original_url={original_url}, api_base={api_base}")
    """將 AI 生成資料寫入 Newtalk DB"""
    api_url = f"{api_base}/InsertPopinArticle"
    
    datas = []
    for item in ai_data:
        # 檢查 key 是否存在
        if "ArticleTitle" not in item or "ArticleContent" not in item:
            print(f"Skipping invalid item (missing keys): {item}")
            continue

        # Title 需轉為 Base64
        title_bytes = item["ArticleTitle"].encode('utf-8')
        title_base64 = base64.b64encode(title_bytes).decode('utf-8')
        
        datas.append({
            "ArticleTitle": title_base64,
            "ArticleContent": item["ArticleContent"]
        })
    
    payload = {
        "OriginalUrl": original_url,
        "Datas": datas
    }
    
    try:
        async with session.post(api_url, headers=HEADERS, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as response:
            resp_text = await response.text()
            if response.status != 200:
                print(f"InsertPopinArticle Failed: Status={response.status}, Response={resp_text}")
            return json.loads(resp_text)
    except Exception as e:
        print(f"Error calling InsertPopinArticle: {e}")
        return None

async def call_anthropic_api(session, title, count=5):
    print(f"Entering call_anthropic_api with title={title}, count={count}")
    """呼叫 Anthropic API 生成內容"""
    prompt = f"""請根據這個主題「{title}」，按以下步驟：
【步驟1：標籤識別】
先從主題和內容中提取所有相關標籤（人物、技術、興趣、產業、地點、現象等）
【步驟2：標籤篩選】
排除以下容易引發爭議的標籤類型：
- 政治類、爭議類、制度類、敏感社會議題類
【步驟3：主題延伸】
基於篩選後的標籤：
1. 最好只有1個標題直接討論原主角/事件
2. {count - 1} 組從科普、知識、實用、趣聞等角度延伸
【輸出要求】
- 每個標題不超過30字
- 每個標題的文章內容600~700字
- 採用台灣新聞標題風格
- 標題要有趣味性和知識性
- 避免爭議性內容
- 文章內容需適當分段，段落之間請務必保留空行以增加閱讀性，每段縮排2格
請直接輸出{count}組高點閱的標題與文章內容，輸出需要{count}組內容用 json 格式，只要資料不需要其它額外文字描述。
格式範例：
[
  {{
    "ArticleTitle": "標題1",
    "ArticleContent": "內容1"
  }},
  ...
]"""

    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    data = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": 10000,
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }
    
    try:
        async with session.post(url, headers=headers, json=data, timeout=aiohttp.ClientTimeout(total=90)) as response:
            resp_text = await response.text()
            print(f"Anthropic API Response: Status={response.status}, Body={resp_text}")

            if response.status == 200:
                result = json.loads(resp_text)
                content = result["content"][0]["text"]
                try:
                    start = content.find('[')
                    end = content.rfind(']') + 1
                    if start != -1 and end != -1:
                        json_str = content[start:end]
                        return json.loads(json_str), None
                    else:
                        return [], f"Could not find JSON in AI response. Raw content: {content}"
                except json.JSONDecodeError as e:
                    return [], f"JSON Parse Error: {e}. Raw content: {content}"
        return [], f"Anthropic API Error: {response.status} - {resp_text}"
    except Exception as e:
        return [], f"Error calling Anthropic API: {e}"

async def call_gemini_api(session, title, count=5):
    print(f"Entering call_gemini_api with title={title}")
    """呼叫 Gemini API 生成內容 (Using google-genai SDK)"""
#     prompt = f"""# Role / 角色設定
# 你是一位精通大數據趨勢與大眾心理的「說故事高手」。你風格幽默、充滿洞見，擅長用淺顯易懂的語言拆解社會現象，讓讀者一旦開始閱讀就「滑梯式」地讀到停不下來。

# # Task / 任務目標
# 請針對主題「{title}」，執行以下步驟並生成 5 組高品質的新聞報導內容。

# ## Step 1：標籤識別與篩選 (Internal Process)
# 1. 提取標籤：從主題中識別人物、技術、興趣、產業、地點、現象等標籤。
# 2. 標籤過濾：嚴格排除「政治、爭議、制度、敏感社會議題」。
# 3. 主題延伸：基於篩選後的標籤生成 5 個切入點：
#    - 1 組直接討論原主角/事件。
#    - 4 組從科普、冷知識、生活實用、奇聞軼事等角度延伸。

# ## Step 2：寫作規範 (Core Formula)
# 每篇文章必須符合以下高品質寫作要求：
# 1. **黃金開頭**：第一段必須在 50 字內引發共鳴或創造懸念，拒絕平鋪直敘。
# 2. **視覺化描述**：多用動詞與感官詞彙（如：硫磺味、扭曲的金屬、閃爍的訊號），少用抽象形容詞。
# 3. **滑梯節奏**：句子短、段落短。禁止使用「首先、其次、最後、綜上所述」等機器味連接詞。
# 4. **台灣新聞風格**：標題需具備點擊誘因（30字內），內文語氣專業中帶有親和力。

# ## Step 3：輸出格式要求
# - 數量：5 組內容。
# - 字數：每篇內文 600-700 字。
# - 排版：內文需適當分段，段落間「務必保留空行」。**每段開頭請縮排 2 格全形空格（　　）**。
# - 格式：僅輸出 JSON 資料，不要任何額外文字描述。

# [
#   {{
#     "ArticleTitle": "標題（30字內）",
#     "ArticleContent": "內容（600-700字，含首行縮排與空行）"
#   }},
#   ...
# ]"""


    prompt = f"""# Role / 角色設定
你是一位資深新聞編輯與專題記者，擅長從單一新聞事件中抽絲剝繭，提供讀者具備「資訊增量」的深度分析。你的寫作風格嚴謹、客觀、具權威性，說話不帶冗餘的修飾詞，重點在於呈現事實背景與邏輯關聯。

# 資訊增量 外部知識融合： 請運用你內建的知識庫，補足該事件在產業史、法律背景或過往類似判例中的數據與事實，使內容具備專業厚度。

# 寫作規範 請依以下規範，撰寫「延伸閱讀文章」：
1. 文章內容需嚴格基於原始新聞的標題合理延伸。
2. 不可改寫原文標題，不得換句話說當作內文。
3. 請提供與主題高度相關的延伸脈絡（背景資訊、前因後果、相關案例、同類型事件、可能後續影響）。
4. 全篇必須與主題緊密相關，不可跳題。
5. 多樣性要求：這 5 組內容需從不同維度切入（例如：法規面向、經濟影響、產業歷史、國際對比、專家觀點），確保讀者在閱讀不同組別時能獲得不重複的新資訊。且請至少在其中一或多組加入與主題有關的「近期時事」。
6. 新聞語氣，禁止使用下列開頭：
   - 「想像一下」 / 「試著想像」 / 「你是否曾經」
   - 任何故事性或情境模擬開場
7. 呈現方式需邏輯清楚、資訊增量明確，不可加入臆測或虛構內容。

原始新聞標題：
《{title}》

## 輸出格式要求
- 數量：5 組內容。
- 字數：每篇內文 600-700 字。
- 排版：內文需適當分段，段落間「務必保留空行」。**每段開頭請縮排 2 格全形空格（　　）**。
- 格式：僅輸出 JSON 資料，不要任何額外文字描述。

[
  {{
    "ArticleTitle": "標題（30字內）",
    "ArticleContent": "內容（600-700字，含首行縮排與空行）"
  }},
  ...
]"""

    try:
        # Mimic successful curl command:
        # Endpoint: https://aiplatform.googleapis.com/v1/publishers/google/models/{model}:generateContent
        url = f"https://aiplatform.googleapis.com/v1/publishers/google/models/{GEMINI_MODEL}:generateContent"
        
        params = {
            "key": GEMINI_API_KEY
        }
        
        headers = {
            "Content-Type": "application/json"
        }
        
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": prompt}
                    ]
                }
            ]
        }
        
        # Debug: Print request info
        print(f"Calling Gemini API (Requests): {url}")
        print(f"Gemini API Prompt: {prompt}")
        
        async with session.post(url, params=params, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=60)) as response:
            resp_text = await response.text()
            
            # Debug: Print full text response
            print(f"Gemini API Response Status: {response.status}")
            print(f"Gemini API Response Text: {resp_text}")
            
            if response.status == 200:
                result = json.loads(resp_text)
                # Extract content from Gemini response structure
                try:
                    content = result["candidates"][0]["content"]["parts"][0]["text"]
                except (KeyError, IndexError) as e:
                    return [], f"Unexpected API response structure: {e}. Raw content: {resp_text}"
                    
                # 嘗試解析 JSON (處理可能的 Markdown code block)
                try:
                    # 尋找 JSON 陣列的開始與結束
                    start = content.find('[')
                    end = content.rfind(']') + 1
                    if start != -1 and end != -1:
                        json_str = content[start:end]
                        return json.loads(json_str), None
                    else:
                        return [], f"Could not find JSON in Gemini response. Raw content: {content}"
                except json.JSONDecodeError as e:
                    return [], f"JSON Parse Error: {e}. Raw content: {content}"
            else:
                 return [], f"Gemini API Error: {response.status} - {resp_text}"
            
    except Exception as e:
        return [], f"Error calling Gemini API: {e}"

async def test_api_response(session, title, provider="gemini", count=5):
    print(f"Entering test_api_response with title={title}, provider={provider}, count={count}")
    """測試 API 回應並直接印出結果"""
    if provider == "gemini":
        result, error = await call_gemini_api(session, title, count)
    else:
        result, error = await call_anthropic_api(session, title, count)
    
    print("----- TEST RESULT -----")
    if error:
        print(f"Error: {error}")
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    print("-----------------------")
    return result

async def get_ai_content(session, title, count=5):
    print(f"Switching AI Provider: {AI_PROVIDER}, count={count}")
    if AI_PROVIDER == "gemini":
        return await call_gemini_api(session, title, count)
    else:
        return await call_anthropic_api(session, title, count)

async def publish_log_message_async(data):
    """Publish log message to Pub/Sub in an async manner"""
    if not publisher:
        logger.error(f"Publisher not initialized. Init Error: {publisher_init_error}")
        return False, f"Publisher not initialized. Init Error: {publisher_init_error}"
        
    try:
        # 轉成 JSON bytes
        data_str = json.dumps(data, ensure_ascii=False)
        data_bytes = data_str.encode("utf-8")
        
        # 發送訊息 (在背景執行緒跑，避免阻塞 event loop)
        loop = asyncio.get_event_loop()
        future = publisher.publish(topic_path, data_bytes)
        message_id = await loop.run_in_executor(None, future.result)
        logger.info(f"Published async message ID: {message_id}")
        return True, None
    except Exception as e:
        logger.error(f"Error publishing message: {e}")
        return False, str(e)

def publish_log_message(data):
    # 為了兼容性保留舊名，但不再於新架構使用
    pass


@functions_framework.http
def process_request(request):
    """HTTP Cloud Function 入口點 - 同步外殼以相容 Functions Framework"""
    return asyncio.run(_process_request_async(request))

async def _process_request_async(request):
    logger.info("Entering _process_request_async")
    """核心的非同步處理邏輯"""
    
    # 處理 CORS
    if request.method == 'OPTIONS':
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Max-Age': '3600'
        }
        return ('', 204, headers)

    headers = {
        'Access-Control-Allow-Origin': '*',
        'Content-Type': 'application/json'
    }

    try:
        request_json = request.get_json(silent=True)
        if not request_json:
            return (json.dumps({"error": "Empty body"}), 400, headers)

        # ---------------------------------------------------------
        # [NEW] Log Mode 處理
        # ---------------------------------------------------------
        if request_json.get('log_mode'):
            logger.info(f"Log Request Received: {request_json}")
            
            # 解析 Media Domain
            media_url = request_json.get('media_url', '')
            media_domain = ''
            if media_url:
                try:
                    parsed = urlparse(media_url)
                    media_domain = parsed.hostname or ''
                except:
                    pass
            
            log_data = {
                "event_type": request_json.get("event_type", "unknown"),
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z", # 雖然前端傳了，後端最好重押
                "media_url": media_url,
                "media_domain": media_domain, # 新增欄位
                "media_title": request_json.get("media_title", ""), # 新增欄位
                "ai_title": request_json.get("ai_title", ""),     # 新增欄位
                "ai_url": request_json.get("ai_url", ""),         # 新增欄位
                "ad_position": request_json.get("ad_position"),
                "pacid": request_json.get("pacid", ""),
                "user_agent": request_json.get("user_agent", request.headers.get("User-Agent", "")),
                "device_type": request_json.get("device_type", ""),
                "ip_address": request.headers.get("X-Forwarded-For", request.remote_addr), # 抓取 IP
                "browser": "", # 簡單用 user_agent 即可，BigQuery 可再解析，或前端傳
                "viewport": request_json.get("viewport", "")
            }
            
            # 發送 Pub/Sub (非同步不會卡頓)
            success, error_msg = await publish_log_message_async(log_data)
            
            if success:
                return (json.dumps({"status": "logged"}), 200, headers)
            else:
                return (json.dumps({"error": f"Logging failed: {error_msg}"}), 500, headers)
        
        # ---------------------------------------------------------
        # 原有 AI 文章生成邏輯
        # ---------------------------------------------------------

        if 'url' not in request_json or 'title' not in request_json:
            return (json.dumps({"error": "Missing url or title parameter"}), 400, headers)
        
        url = request_json['url']
        title = request_json['title']

        async with aiohttp.ClientSession() as session:
            # [NEW] 測試模式
            if request_json.get('test_mode'):
                provider = request_json.get('provider', 'gemini') # 預設測試 gemini
                count = request_json.get('count', 5)
                print(f"Test Mode Activated: provider={provider}, count={count}")
                test_result = await test_api_response(session, title, provider, count)
                return (json.dumps(test_result, ensure_ascii=False), 200, headers)
            
            # 1. 清理 URL
            clean_target_url = clean_url(url)
            print(f"Processing URL: {clean_target_url}")

            # 1.5 根據 URL 決定 API base
            api_base = get_api_base_from_url(url)
            print(f"Using API Base: {api_base}")

            # 2. 第一次查詢 DB
            check_result = await get_popin_article(session, clean_target_url, api_base)
            
            existing_data = [] # Data we have so far
            if check_result and check_result.get("isSuccess") and check_result.get("data"):
                existing_data = check_result["data"]
                print(f"Cache Hit: Found {len(existing_data)} existing articles")
            
            # 3. 計算需要補足的數量 (目標 5 篇)
            target_total = 5
            shortfall = target_total - len(existing_data)
            
            final_data = existing_data
            
            if shortfall > 0:
                print(f"Shortfall detected or Cache Miss: Need {shortfall} more articles (Have {len(existing_data)})")
                
                # 呼叫 AI 補足
                ai_content, error_msg = await get_ai_content(session, title, count=shortfall)
                
                if ai_content:
                    # 4. 寫入 DB
                    insert_result = await insert_popin_article(session, clean_target_url, ai_content, api_base)
                    if insert_result and insert_result.get("isSuccess"):
                        print("Insert Success")
                        # 5. 再次查詢 DB 以獲取完整資料
                        recheck_result = await get_popin_article(session, clean_target_url, api_base)

                        # 若重抓失敗或無資料，嘗試重試
                        if not (recheck_result and recheck_result.get("isSuccess") and recheck_result.get("data")):
                            print("Re-fetch empty or failed. Waiting to retry...")
                            await asyncio.sleep(1) # async delay
                            recheck_result = await get_popin_article(session, clean_target_url, api_base)

                        if recheck_result and recheck_result.get("isSuccess") and recheck_result.get("data"):
                            print(f"Re-fetch Success: Found {len(recheck_result['data'])} articles")
                            final_data = recheck_result["data"]
                        else:
                             print(f"Re-fetch Failed after retry. Result: {recheck_result}")
                    else:
                        print(f"Insert Failed: {insert_result}")
                else:
                    print(f"AI Generation Failed: {error_msg}")
            else:
                print("Sufficient articles found, skipping AI generation.")
            
            # 6. 整理回傳資料
            response_data = []
            for item in final_data[:3]:
                response_data.append({
                    "title": item.get("ArticleTitle", ""),
                    "url": item.get("ArticleUrl", "")
                })
                
            return (json.dumps(response_data, ensure_ascii=False), 200, headers)

    except Exception as e:
        print(f"System Error: {e}")
        return (json.dumps({"error": str(e)}), 500, headers)
