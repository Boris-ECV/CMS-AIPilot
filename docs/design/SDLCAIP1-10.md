# 設計文件 — SDLCAIP1-10 後台登入 JWT/Session

## 對應需求規格
G1 通過版本(2026-08-11 進入 Designing):單一後台 admin 帳號透過
`POST /login`(username/password)取得 JWT,用於存取受保護的文章 API。
JWT: HS256、payload 至少含 sub/iat/exp、8 小時效期,回傳
`{"access_token": ..., "token_type": "bearer"}`。憑證存放於 AWS SSM
Parameter Store SecureString。登入失敗 5 次鎖定帳號 15 分鐘,鎖定期間
回傳 429 並附剩餘時間;登入成功需重置失敗計數為 0。失敗計數與鎖定到期
時間存於 DynamoDB(單一 item)。需對外提供 token 驗證函式供
SDLCAIP1-11 當作 FastAPI dependency 使用。範圍不含:保護
`/articles` 端點本身(SDLCAIP1-11 負責)、登出/撤銷、多使用者/RBAC、
忘記密碼、refresh token。

## 介面/API 契約

### `POST /login`

Request body (`application/json`):
```json
{
  "username": "string",
  "password": "string"
}
```
對應 Pydantic model `LoginRequest(BaseModel)`:
- `username: str = Field(min_length=1)`
- `password: str = Field(min_length=1)`

Response — 200 OK（登入成功，且會將該帳號的失敗計數重置為 0）:
```json
{
  "access_token": "<JWT string>",
  "token_type": "bearer"
}
```
對應 Pydantic model `TokenResponse(BaseModel)`。

Response — 401 Unauthorized（帳號未鎖定、但帳密錯誤；此次失敗會使
失敗計數 +1，若因此達到第 5 次則同時設定 `locked_until`）:
```json
{"detail": "Invalid username or password"}
```

Response — 429 Too Many Requests（帳號目前處於鎖定狀態；本次嘗試
**不**再累加失敗計數，因為帳號已鎖定，累加無意義且會不必要延長觀測
窗口以外的狀態變化）:
```json
{"detail": "Account locked. Try again in 612 seconds.", "retry_after_seconds": 612}
```
同時設定 HTTP header `Retry-After: 612`（秒數,向下取整,最小為 0）。

狀態碼摘要：200 成功 / 401 帳密錯誤未鎖定 / 429 帳號鎖定中。
不使用 403,因為此端點不涉及授權層級,只有「有效登入」與「無效登入」
二態,401 語意最貼近。

### 提供給 SDLCAIP1-11 的 token 驗證函式

新增模組 `src/cms_aipilot/auth.py`,匯出：

```python
def decode_access_token(token: str) -> dict | None:
    """驗證 JWT 簽章與效期。

    成功回傳解碼後的 payload(dict,至少含 sub/iat/exp)。
    簽章錯誤、格式錯誤、或已過期一律回傳 None,不拋出未捕捉例外
    ——呼叫端（SDLCAIP1-11 的 FastAPI dependency）可直接依 None
    判斷並轉成 401,不需要在每個呼叫點包 try/except 特定的
    jwt 例外型別。
    """
```

SDLCAIP1-11 預期會在自己的模組內用
`OAuth2PasswordBearer`／`Depends` 包一層來從 `Authorization: Bearer`
header 取出 token 字串,再呼叫 `decode_access_token(token)`——header
解析與「保護哪些路由」屬於 SDLCAIP1-11 範圍,本 story 只交付上述
純函式。

## 資料模型

### DynamoDB:登入鎖定狀態表

新增資料表,環境變數名稱沿用既有 `ARTICLES_TABLE_NAME` 命名慣例：
`AUTH_TABLE_NAME`。

Partition key: `id`（String,固定常數值 `"admin_login_state"`）。
因為 spec 明確只有單一 admin 帳號,不需要用 username 當 PK,用固定
常數字串比用 username 當 key 更明確表達「這是單例狀態,不是使用者
資料表」的意圖,也避免未來誤以為此表可以存多筆使用者。

Item 屬性：
| 屬性 | 型別 | 說明 |
|---|---|---|
| `id` | S | 固定值 `"admin_login_state"`（partition key） |
| `failed_attempts` | N | 連續失敗次數,登入成功時重置為 0 |
| `locked_until` | N（epoch seconds,可省略/為 0） | 鎖定到期時間;不存在或 ≤ 目前時間代表未鎖定 |

不建立額外索引(單一 item,不需要 GSI/LSI)。首次登入時該 item 可能
不存在,存取層需以 `get_item` 取不到時視為 `failed_attempts=0`、
未鎖定,沿用既有 `get_articles_table()` 的 lazy-resource 模式新增
`get_auth_table()`。

### 無其他新增資料表
不新增文章相關資料模型變更。

## 關鍵技術決策

1. **簽章金鑰不落地成一般環境變數,改用 SSM 參數名稱當環境變數值**
   ——沿用 `ARTICLES_TABLE_NAME` 的慣例(環境變數存「資源識別」而非
   機密本身),新增：
   - `JWT_SECRET_SSM_PARAM`：JWT HS256 簽章金鑰的 SSM 參數名稱
     （SecureString）
   - `ADMIN_USERNAME_SSM_PARAM`：admin 帳號的 SSM 參數名稱
   - `ADMIN_PASSWORD_HASH_SSM_PARAM`：admin 密碼雜湊的 SSM 參數名稱
     （bcrypt hash,不存明文密碼）

   對應 SSM 參數的實際命名建議：
   - `/cms-aipilot/auth/jwt-secret`
   - `/cms-aipilot/auth/admin-username`
   - `/cms-aipilot/auth/admin-password-hash`

   （實際部署時的參數路徑由環境變數指定,上述僅為建議預設值,IaC/部署
   設定可覆寫,不寫死在程式碼中。）

2. **SSM 值採 process 內快取,不做 per-request 呼叫**——Lambda cold
   start 時第一次呼叫 `boto3.client("ssm").get_parameter` 取得三個
   參數值後快取在 module-level 變數（用 `functools.lru_cache`
   包裝的 getter,行為類似既有 `get_articles_table()` 的 lazy
   建立模式,但多一層快取,因為金鑰/帳密不像 DynamoDB table
   resource 那樣需要每次重建,且 SSM API 呼叫有延遲與費率限制,
   每個請求都打一次不合理）。測試時比照現有 boto3 mock 慣例
   （moto / monkeypatch boto3 client）mock `ssm` client。

3. **密碼比對使用 bcrypt hash,而非明文存 SSM**——SecureString 已
   加密儲存,但比對邏輯仍用 `bcrypt.checkpw`,避免明文密碼出現在
   任何日誌/例外訊息中,也符合一般密碼儲存最佳實務。

4. **429 鎖定期間不再累加失敗計數**——避免鎖定期間內反覆嘗試導致
   `locked_until` 被非預期地重新計算或造成計數溢位;鎖定期間的請求
   純粹只讀狀態、比較目前時間與 `locked_until`。

5. **`decode_access_token` 回傳 `None` 而非拋例外**——這是
   SDLCAIP1-11 明確要求的介面約定（spec 原文:
   「失敗不拋出未處理例外」),讓下游 dependency 可以用簡單的
   `if payload is None: raise HTTPException(401)` 處理,不需要
   認識 `jwt` 套件的例外階層。

6. **JWT library 選用 PyJWT**——與 FastAPI 官方文件範例一致、
   HS256 為標準支援演算法,pyproject.toml 需新增依賴
   `pyjwt`（另需 `bcrypt` 供密碼雜湊比對）。

## 開放設計問題(定稿時必須為空)
無
