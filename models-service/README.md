# models-service — AI Model Gateway

Xem tài liệu chi tiết tại [`docs/README.md`](./docs/README.md).

## Quick Start

```bash
cd models-service
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

## Cấu Hình Tối Thiểu `.env`

```env
MODEL_NAME=gpt-4.1-mini
API_KEY=your_api_key_here
BASE_URL=https://api.openai.com/v1
PROMPT_SERVICE_URL=http://localhost:8001
```
