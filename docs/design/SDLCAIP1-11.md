# 設計文件 — SDLCAIP1-11 後台文章 API 掛上認證保護

## 對應需求規格
G1 通過版本(見 `docs/PRD.md` SDLCAIP1-11 章節):將 SDLCAIP1-10 提供的 JWT
驗證函式,以 FastAPI 依賴(dependency)的形式套用在全部 5 個現存文章端點——
`POST /articles`、`GET /articles`、`GET /articles/{article_id}`、
`PUT /articles/{article_id}`、`DELETE /articles/{article_id}`
(對應已 Done 的 SDLCAIP1-4/5/6/7)。缺失/無效/逾期的 Authorization
header/token 一律回傳 401,不得使伺服器崩潰。現有端點的商業邏輯與成功路徑
回應結構不變。`GET /health`(SDLCAIP1-2)不在保護範圍內。

**SDLCAIP1-10 設計文件狀態:** 撰寫本文件當下 `docs/design/SDLCAIP1-10.md`
尚不存在(SDLCAIP1-10 與本票同時通過 G1、同時進入 Designing)。本設計改依
SDLCAIP1-10 在 Jira 需求規格 / `docs/PRD.md` 中已定案的呼叫契約設計:一個
令牌驗證函式,驗證 JWT 簽章與過期時間(HS256),成功時回傳解析後的 payload
(至少含 `sub`/`iat`/`exp`),失敗時不得拋出未攔截例外(HTTPException 除外)。
本文件將此函式以 `validate_token(token: str) -> dict` 的簽章佔位表示;若
SDLCAIP1-10 定稿後函式名稱/模組路徑不同,developer 需依實際簽章調整 import,
不影響本文件其餘設計(依賴掛載方式、401 回應格式)。

## 介面/API 契約

**現有 5 個端點的路徑、方法、request/response 格式、成功狀態碼不變**——本票
不修改業務邏輯,僅新增認證檢查層。

**新增行為:認證失敗時的 401 回應**

所有受保護端點在認證失敗時,回傳:

- 狀態碼:`401 Unauthorized`
- Header:`WWW-Authenticate: Bearer`
- Body(沿用專案既有 `HTTPException(detail=...)` → FastAPI 預設錯誤格式,
  與現有 404 錯誤處理風格一致,見 `main.py` 中 `HTTPException(status_code=404, detail=...)`):

```json
{
  "detail": "Not authenticated"
}
```

失敗情境一律映射到同一 401 + 上述 body,不區分「缺 header」/「格式錯誤」/
「簽章無效」/「已過期」四種原因於 response body 中(規格僅要求「回傳
401」,未要求區分錯誤訊息;避免對外洩漏驗證失敗細節)。

**依賴掛載方式**

現況(`src/cms_aipilot/main.py`)5 個文章端點皆直接註冊於 `app`
(`@app.post/get/put/delete`),未使用 `APIRouter`。本票將此 5 個端點改掛到
一個新的 `APIRouter`,並在該 router 層級套用共用依賴,而非逐一在每個路由
加 `Depends()`——理由見下方「關鍵技術決策」。

```python
from fastapi import APIRouter, Depends

articles_router = APIRouter(dependencies=[Depends(require_auth)])

@articles_router.post("/articles", status_code=201)
def create_article(...): ...

@articles_router.get("/articles")
def list_articles(...): ...

@articles_router.get("/articles/{article_id}")
def get_article(...): ...

@articles_router.put("/articles/{article_id}")
def update_article(...): ...

@articles_router.delete("/articles/{article_id}", status_code=204)
def delete_article(...): ...

app.include_router(articles_router)
```

`app.get("/health")` 維持直接掛在 `app` 上,不受影響。

**`require_auth` 依賴函式(本票新增,薄封裝)**

```python
from fastapi import Header, HTTPException
from fastapi.security.utils import get_authorization_scheme_param

def require_auth(authorization: str | None = Header(default=None)) -> dict:
    scheme, token = get_authorization_scheme_param(authorization or "")
    if not authorization or scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = validate_token(token)  # SDLCAIP1-10 提供的驗證函式
    if payload is None:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload
```

`validate_token` 的確切 import 路徑與失敗時的回傳約定(回傳 `None` vs 拋出
特定例外)以 SDLCAIP1-10 定稿設計為準;若其失敗時是拋出自訂例外而非回傳
`None`,developer 改為 `try/except` 捕捉該例外並轉譯為上述 401
`HTTPException`,不需回到本設計文件重新走 G1b。此為實作期依實際簽章微調,
非規格變更。

## 資料模型
無新增資料模型。本票僅新增認證守衛,不新增/變更任何資料表、欄位或索引。

## 關鍵技術決策

- **改用 `APIRouter(dependencies=[...])` 而非逐路由 `Depends()`:**
  5 個端點全數且僅需保護(無例外),用 router 層級依賴一次套用,避免 5 處
  重複程式碼與遺漏風險;符合本票「<=1 dev-day、只掛一個共用依賴」的規模
  定位。
- **401 錯誤不區分失敗原因於回應內容:** 規格只要求「缺失/無效/逾期→
  401」,未定義三種情況要回不同訊息;為避免對外部呼叫者洩漏驗證失敗細節
  (常見安全實踐),統一回傳同一 `detail`。
- **`require_auth` 回傳解析後的 payload(而非 `None`):** 雖然目前 5 個端點
  皆不使用呼叫者身分(單一管理者、無 RBAC),但依 FastAPI 慣例讓依賴回傳
  有意義的值,便於未來若有端點需要讀取 `sub` 時可直接用
  `Depends(require_auth)` 取值,不需重構依賴本身簽章。
- **驗證失敗不得讓伺服器崩潰:** `require_auth` 只捕捉/轉譯例外為
  `HTTPException`,不吞噬非預期例外(如 SDLCAIP1-10 內部 bug 拋出的其他
  例外),保留 FastAPI 預設的 500 處理,避免掩蓋真正的程式錯誤;此為依循
  規格「不得 crash」= 不得未攔截地讓 500 以外的失敗模式发生,而非「吞掉
  所有例外」。

## 開放設計問題(定稿時必須為空)
無。
