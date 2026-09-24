# prompt-service — Meta Prompt Engine

Xem tài liệu chi tiết tại [`docs/README.md`](./docs/README.md).

## Quick Start

```bash
cd prompt-service
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8001
```

## Cấu Trúc Thư Mục

```
prompt-service/
├── app/                        # Source code FastAPI
├── prompt_architechture/       # Template meta-prompt (hệ thống)
│   ├── system_prompt.md        # Jinja2 master template
│   ├── AGENTS.md               # Luật hành xử agent
│   ├── IDENTITY.md             # Danh tính AI
│   ├── SOUL.md                 # Cá tính, giọng điệu
│   ├── TOOLS.md                # Tool policies
│   ├── USER.md                 # Hồ sơ user (template mặc định)
│   └── MEMORY.md               # Bộ nhớ dài hạn (template mặc định)
├── docs/
│   └── README.md               # Tài liệu đầy đủ
└── .env
```
