import functions_framework
import requests
import json
import base64
import os
from urllib.parse import urlparse
from google.cloud import pubsub_v1
import datetime
import logging
import asyncio
import aiohttp
from dotenv import load_dotenv
import hashlib
from google.cloud import firestore

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
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite-preview")
AI_PROVIDER = os.environ.get("AI_PROVIDER", "gemini")  # anthropic 或 gemini
FIRESTORE_DB_NAME = os.environ.get("FIRESTORE_DB_NAME", "ai-ad-generate-db")

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
GENERATE_TOPIC_ID = "popin-ai-ad-generate-topic"

# Initialize Pub/Sub Publisher and Firestore Client
publisher = None
db = None
publisher_init_error = None
topic_path = None
ai_topic_path = None

if not PROJECT_ID:
    publisher_init_error = "Could not determine GCP Project ID. Please set GCP_PROJECT_ID env var."
    logger.error(publisher_init_error)
else:
    try:
        publisher = pubsub_v1.PublisherClient()
        topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)
        ai_topic_path = publisher.topic_path(PROJECT_ID, GENERATE_TOPIC_ID)
        logger.info(f"Pub/Sub initialized. topic: {topic_path}, ai_topic: {ai_topic_path}")
    except Exception as e:
        publisher_init_error = str(e)
        logger.error(f"Failed to initialize Pub/Sub publisher: {e}")
        
    try:
        db = firestore.Client(project=PROJECT_ID, database=FIRESTORE_DB_NAME)
        logger.info(f"Firestore client initialized successfully (DB: {FIRESTORE_DB_NAME}).")
    except Exception as e:
        logger.error(f"Failed to initialize Firestore Client: {e}")

# ---------------------------------------------------------
# [NEW] Lock 機制與工作推送 (方案 B)
# ---------------------------------------------------------
def try_acquire_lock(url):
    """嘗試取得該 URL 的處理鎖，過期時間為 3 分鐘。"""
    if not db:
        logger.error("Firestore DB is not initialized, bypassing lock (will return True).")
        return True
        
    try:
        doc_id = hashlib.md5(url.encode('utf-8')).hexdigest()
        doc_ref = db.collection('ai_article_locks').document(doc_id)
        transaction = db.transaction()
        
        @firestore.transactional
        def _update_in_transaction(t, ref):
            snapshot = ref.get(transaction=t)
            now = datetime.datetime.utcnow()
            
            if snapshot.exists:
                data = snapshot.to_dict()
                locked_until = data.get("locked_until")
                if locked_until and locked_until.replace(tzinfo=None) > now:
                    return False
            
            t.set(ref, {
                "url": url,
                "status": "processing",
                "locked_until": now + datetime.timedelta(minutes=3)
            })
            return True
            
        return _update_in_transaction(transaction, doc_ref)
    except Exception as e:
        logger.error(f"Error acquiring lock: {e}")
        return True

def load_custom_config(domain):
    """載入特定網域的自訂設定檔"""
    try:
        config_path = os.path.join(os.path.dirname(__file__), f"{domain}.json")
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading custom config for {domain}: {e}")
    return None

def release_lock(url):
    """手動釋放鎖 (任務完成後調用)"""
    if not db:
        return
    try:
        doc_id = hashlib.md5(url.encode('utf-8')).hexdigest()
        db.collection('ai_article_locks').document(doc_id).delete()
    except Exception as e:
        logger.error(f"Error releasing lock: {e}")

async def publish_generate_task_async(url, title, shortfall, api_base, config_name=None):
    if not publisher or not ai_topic_path:
        return False, "Publisher or ai_topic_path not initialized"
    try:
        data = {"url": url, "title": title, "shortfall": shortfall, "api_base": api_base, "config_name": config_name}
        data_str = json.dumps(data, ensure_ascii=False)
        data_bytes = data_str.encode("utf-8")
        loop = asyncio.get_running_loop()
        future = publisher.publish(ai_topic_path, data_bytes)
        message_id = await loop.run_in_executor(None, future.result)
        logger.info(f"Published AI generation task ID: {message_id}")
        return True, None
    except Exception as e:
        logger.error(f"Error publishing task: {e}")
        return False, str(e)

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
        print(f"Error testing URL {original_url}: {e}")
        return DEFAULT_API_BASE

async def call_anthropic_api(session, title, count=5, custom_config=None, source_url=None):
    print(f"Entering call_anthropic_api with title={title}")
    
    json_format_rules = f"""
## 輸出格式要求
- 數量：{count} 組內容。
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

    if custom_config:
        instruction = custom_config.get("instruction", "")
        prompt = instruction.replace("{title}", title) + "\n\n" + json_format_rules
        temperature = custom_config.get("temperature", 0.7)
    else:
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
{json_format_rules}"""
        temperature = 0.7

    try:
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        
        payload = {
            "model": ANTHROPIC_MODEL,
            "max_tokens": 4000,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}]
        }
        
        async with session.post(url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=90)) as response:
            resp_text = await response.text()
            print(f"Anthropic API Response: Status={response.status}, Body={resp_text}")

            if response.status == 200:
                result = json.loads(resp_text)
                text_content = result.get("content", [])[0].get("text", "")
                
                try:
                    start = text_content.find('[')
                    end = text_content.rfind(']') + 1
                    if start != -1 and end != -1:
                        json_str = text_content[start:end]
                        return json.loads(json_str), None
                    else:
                        return [], f"Could not find JSON in AI response. Raw content: {text_content}"
                except json.JSONDecodeError as e:
                    return [], f"JSON Parse Error: {e}. Raw content: {text_content}"
            else:
                return [], f"Anthropic API Error: {response.status} - {resp_text}"
    except Exception as e:
        return [], f"Error calling Anthropic API: {e}"

async def call_gemini_api(session, title, count=5, custom_config=None, source_url=None):
    print(f"Entering call_gemini_api with title={title}, count={count}")
    
    json_format_rules = f"""
## 輸出格式要求
- 數量：{count} 組內容。
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

    if custom_config:
        instruction = custom_config.get("instruction", "")
        prompt = instruction.replace("{title}", title) + "\n\n" + json_format_rules
        temperature = custom_config.get("temperature", 0.7)
    else:
        prompt = f"""# Role / 角色設定
你是一位資深新聞編輯與專題記者，擅長從單一新聞事件中抽絲剝繭，提供讀者具備「資訊增量」的深度分析。你的寫作風格嚴謹、客觀、具權威性，說話不帶冗餘的修飾詞，重點在於呈現事實背景與邏輯關聯。

# 資訊增量 外部知識融合： 請運用你內建的知識庫，補足該事件在產業史、法律背景或過往類似判例中的數據與事實，使內容具備專業厚度。

# 寫作規範 請依以下規範，撰寫「延伸閱讀文章」：
1. 文章內容需嚴格基於原始新聞的標題合理延伸。
2. 文章內文可承接原文標題之重點進行撰寫，但不得直接複製或僅以改寫標題作為單一段落內容。文章標題需與原文標題語意相關，但不得完全相同。文章標題可進行適度改寫，但不得偏離原文重點或新增未提及資訊。
3. 請提供與主題高度相關的延伸脈絡（背景資訊、前因後果、相關案例、同類型事件、可能後續影響）。
4. 全篇必須與主題緊密相關，不可跳題。
5. 多樣性要求：這 {count} 組內容需從不同維度切入（例如：法規面向、經濟影響、產業歷史、國際對比、專家觀點），確保讀者在閱讀不同組別時能獲得不重複的新資訊。且請至少在其中一或多組加入與主題有關的「近期時事」。
6. 新聞語氣，禁止使用下列開頭：
   - 「想像一下」 / 「試著想像」 / 「你是否曾經」
   - 任何故事性或情境模擬開場
7. 呈現方式需邏輯清楚、資訊增量明確，不可加入臆測或虛構內容。

原始新聞標題：
《{title}》

{json_format_rules}"""
        temperature = 0.7

    # 僅在「有帶 config_name（custom_config）」且有合法新聞網址時，啟用 url_context 讓 Gemini 直接讀原文內文當素材；
    # 正式預設路徑（無 config_name）維持原樣、不受影響。
    use_url_context = bool(custom_config) and bool(source_url) and str(source_url).startswith("http")
    if use_url_context:
        prompt += f"\n\n請先讀取下列新聞網址的完整內文，作為撰寫的主要素材（標題與內文都要貼合內文事實）：\n{source_url}"

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
            ],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": 6000,
                "responseMimeType": "application/json",
                "thinkingConfig": {
                    "includeThoughts": False,
                    #"thinkingLevel": "minimal"
                    "thinkingBudget": 0
                }
            }
        }
        
        # 啟用 url_context 工具：讓 Gemini 讀取 source_url 的內文
        if use_url_context:
            payload["tools"] = [{"url_context": {}}]

        # Debug: Print request info
        print(f"Calling Gemini API (Requests): {url}")
        print(f"Gemini API Prompt: {prompt}")
        
        async with session.post(url, params=params, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=120 if use_url_context else 60)) as response:
            resp_text = await response.text()
            
            # Debug: Print full text response
            print(f"Gemini API Response Status: {response.status}")
            print(f"Gemini API Response Text: {resp_text}")
            
            if response.status == 200:
                result = json.loads(resp_text)
                # Extract content from Gemini response structure
                try:
                    content_text = result["candidates"][0]["content"]["parts"][0]["text"]
                except (KeyError, IndexError) as e:
                    return [], f"Unexpected API response structure: {e}. Raw content: {resp_text}"
                    
                # 嘗試解析 JSON (處理可能的 Markdown code block)
                try:
                    # 尋找 JSON 陣列的開始與結束
                    start = content_text.find('[')
                    end = content_text.rfind(']') + 1
                    if start != -1 and end != -1:
                        json_str = content_text[start:end]
                        return json.loads(json_str), None
                    else:
                        return [], f"Could not find JSON in Gemini response. Raw content: {content_text}"
                except json.JSONDecodeError as e:
                    return [], f"JSON Parse Error: {e}. Raw content: {content_text}"
            else:
                 return [], f"Gemini API Error: {response.status} - {resp_text}"
            
    except Exception as e:
        return [], f"Error calling Gemini API: {e}"

async def test_api_response(session, title, provider="gemini", count=5, custom_config=None, source_url=None):
    print(f"Entering test_api_response with title={title}, provider={provider}, count={count}")
    """測試 API 回應並直接印出結果"""
    if provider == "gemini":
        result, error = await call_gemini_api(session, title, count, custom_config, source_url)
    else:
        result, error = await call_anthropic_api(session, title, count, custom_config, source_url)
    
    print("----- TEST RESULT -----")
    if error:
        print(f"Error: {error}")
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    print("-----------------------")
    return result

async def get_ai_content(session, title, count=5, custom_config=None, source_url=None):
    print(f"Switching AI Provider: {AI_PROVIDER}, count={count}")
    if AI_PROVIDER == "gemini":
        return await call_gemini_api(session, title, count, custom_config, source_url)
    else:
        return await call_anthropic_api(session, title, count, custom_config, source_url)

async def publish_log_message_async(data):
    """Publish log message to Pub/Sub in an async manner"""
    if not publisher or not topic_path:
        logger.error(f"Publisher or topic_path not initialized. Init Error: {publisher_init_error}")
        return False, f"Publisher or topic_path not initialized. Init Error: {publisher_init_error}"
        
    try:
        # 轉成 JSON bytes
        data_str = json.dumps(data, ensure_ascii=False)
        data_bytes = data_str.encode("utf-8")
        
        # 發送訊息 (在背景執行緒跑，避免阻塞 event loop)
        loop = asyncio.get_running_loop()
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
        config_name = request_json.get('config_name', '') # 取得自訂設定名稱

        async with aiohttp.ClientSession() as session:
            # [NEW] 測試模式
            if request_json.get('test_mode'):
                provider = request_json.get('provider', 'gemini') # 預設測試 gemini
                count = request_json.get('count', 5)
                # 測試模式也可以載入 config_name 進行測試
                custom_config = load_custom_config(config_name) if config_name else None
                print(f"Test Mode Activated: provider={provider}, count={count}, config={config_name}")
                test_result = await test_api_response(session, title, provider, count, custom_config, source_url=url)
                return (json.dumps(test_result, ensure_ascii=False), 200, headers)
            
            # 1. 清理 URL
            clean_target_url = clean_url(url)
            print(f"Processing URL: {clean_target_url}")

            # 1.6 根據 URL 決定 API base (原 newtalk.tw PopIn 邏輯)
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
                
                # [方案 B] 呼叫 Lock 與異步發送，完全不卡住 HTTP
                if try_acquire_lock(clean_target_url):
                    success, error_msg = await publish_generate_task_async(
                        url=clean_target_url,
                        title=title,
                        shortfall=shortfall,
                        api_base=api_base,
                        config_name=config_name
                    )
                    if success:
                        print(f"Lock acquired, task published for {clean_target_url}")
                    else:
                        print(f"Lock acquired but failed to publish task for {clean_target_url}: {error_msg}")
                        release_lock(clean_target_url) # 發佈失敗，撤銷鎖
                else:
                    print(f"Task already running or locked for {clean_target_url}, HTTP skipped.")
                
                # 回傳 processing 狀態，讓前端維持 loading 並啟動 polling
                return (json.dumps({"status": "processing"}, ensure_ascii=False), 200, headers)
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

# ---------------------------------------------------------
# [NEW] 背景端 Worker 進入點
# ---------------------------------------------------------
@functions_framework.cloud_event
def process_pubsub_worker(cloud_event):
    """
    Background worker triggered by Pub/Sub 'popin-ai-ad-generate-topic'.
    專職處理耗時的 AI 生成工作與寫入 DB。
    """
    return asyncio.run(_process_pubsub_worker_async(cloud_event))

async def _process_pubsub_worker_async(cloud_event):
    logger.info("Entering _process_pubsub_worker_async")
    
    url = None
    try:
        if not cloud_event or not cloud_event.data or 'message' not in cloud_event.data:
            logger.error("Invalid cloud_event payload")
            return
            
        message_data = cloud_event.data['message']['data']
        message_id = cloud_event.data['message'].get('messageId', '')
        # Pub/Sub payload is base64 encoded
        decoded_data = base64.b64decode(message_data).decode("utf-8")
        task_info = json.loads(decoded_data)

        url = task_info.get("url")
        title = task_info.get("title")
        shortfall = task_info.get("shortfall", 5)
        api_base = task_info.get("api_base", DEFAULT_API_BASE)
        config_name = task_info.get("config_name", "")
        # 正式生成的「預設 prompt」：前端未帶 config_name 時，套用環境變數 DEFAULT_CONFIG_NAME 指定的 config（預設 newtalk）。
        # 客戶選定方向後，只要在 ai-ad-generate 改這個環境變數即可秒切換（newtalk / newtalk_a / newtalk_b），不需動 code。
        if not config_name:
            config_name = os.environ.get("DEFAULT_CONFIG_NAME", "newtalk")

        if not url or not title:
            logger.error("Missing url or title in pubsub task")
            return

        # Pub/Sub at-least-once 去重：用 messageId 確保同一筆訊息只處理一次
        if db and message_id:
            dedup_ref = db.collection('processed_pubsub_messages').document(message_id)
            try:
                dedup_ref.create({
                    "url": url,
                    "processed_at": datetime.datetime.utcnow(),
                    "expire_at": datetime.datetime.utcnow() + datetime.timedelta(days=1)
                })
                logger.info(f"Message {message_id} registered for processing.")
            except Exception as e:
                if 'already exists' in str(e).lower() or 'ALREADY_EXISTS' in str(e):
                    logger.info(f"Duplicate message {message_id}, skipping.")
                    return
                else:
                    logger.warning(f"Dedup check failed ({e}), proceeding anyway.")

        logger.info(f"Background Task Started for: {url}, Need {shortfall} articles")

        async with aiohttp.ClientSession() as session:
            # 如果有收到 config_name，才讀取 custom config
            custom_config = load_custom_config(config_name) if config_name else None
            ai_content, error_msg = await get_ai_content(session, title, count=shortfall, custom_config=custom_config, source_url=url)
            
            if ai_content:
                insert_result = await insert_popin_article(session, url, ai_content, api_base)
                if insert_result and insert_result.get("isSuccess"):
                    logger.info(f"Background Task Insert Success for {url}")
                else:
                    logger.error(f"Background Task Insert Failed: {insert_result}")
            else:
                logger.error(f"Background AI Generation Failed: {error_msg}")
                
    except Exception as e:
        logger.error(f"Error in background worker: {e}")
    finally:
        # 解除 Lock
        if url:
             release_lock(url)
             logger.info(f"Released lock for {url}")
