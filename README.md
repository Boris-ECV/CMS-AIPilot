# CMS AI Pilot

具備前後台的 CMS 系統。後台提供網頁介面編輯文章,發布後產生全靜態 HTML 檔案並上傳覆蓋 AWS S3;前台完全是靜態檔案,不拉資料庫內容。

技術棧:Python (FastAPI + Mangum) on AWS Lambda、DynamoDB、S3、React + Vite(後台介面)、AWS CDK(IaC)。

本 repo 使用 [SDLC Agent Framework](docs/00-handover.md) 驅動開發流程,細節見 `docs/`、`project-profile.yaml`。

## 本機開發

```
pip install -e ".[dev]"
playwright install --with-deps chromium
pytest -q
ruff check .
```
