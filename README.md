<a id="readme-top"></a>

<div align="center">
  <img src="images/logo.png.jpeg" alt="Sale Magic AI" width="400" />

  <br />
  <br />

  **AN AI SALES ASSISTANT THAT SELLS LIKE A HUMAN — ON ZALO**

  [![Contributors][contributors-shield]][contributors-url]
  [![Forks][forks-shield]][forks-url]
  [![Stargazers][stars-shield]][stars-url]
  [![Issues][issues-shield]][issues-url]
  [![GPL v3 License][license-shield]][license-url]

  A multi-service AI chatbot that lives inside **Zalo** — Vietnam's #1 messaging app.<br />
  It remembers who you are, discovers what you need, and walks you through a complete purchase<br />
  using **SPIN Selling** methodology — from "hello" to order confirmation — through natural conversation.

  [Explore the Docs](https://github.com/magic-sales/magic-sale-ai) · [Report Bug](https://github.com/magic-sales/magic-sale-ai/issues/new?labels=bug&template=bug-report---.md) · [Request Feature](https://github.com/magic-sales/magic-sale-ai/issues/new?labels=enhancement&template=feature-request---.md)

</div>

---

## The Idea

Most e-commerce chatbots dump a product list the moment you say "hi". That's a search engine with a chat bubble — not selling.

**Magic Sale AI** implements **SPIN Selling** as an AI agent. It first *understands who you are*, then *discovers what you need*, then *recommends the right product*, and only then *closes the sale*. If you say "no", it handles objections like a trained salesperson (up to 3 times, then gracefully exits).

Every conversation feels like talking to a knowledgeable friend, not a robot.

---

## Highlights

- **[Sells like a human](#spin-selling--the-sales-methodology-inside-the-ai)** — 5-phase sales flow (Opening → Discovery → Recommendation → Objection Handling → Closing) powered by SPIN Selling
- **[Remembers every customer](#memory--short-term-and-long-term)** — per-user memory that evolves with each conversation: name, preferences, health conditions, past purchases
- **[One prompt, many personalities](#the-prompt-architecture--why-every-conversation-feels-different)** — modular prompt architecture stored in PostgreSQL, assembled per-customer at request time
- **[Smart product search](#mcp-tools--what-the-ai-can-actually-do)** — hybrid search combining full-text keywords + semantic vector similarity (RAG)
- **[End-to-end ordering](#mcp-tools--what-the-ai-can-actually-do)** — from "I'll take one" to inventory validation, ACID transactions, and email confirmation — all inside the chat
- **[Tool-calling AI agent](#mcp-tools--what-the-ai-can-actually-do)** — built on Model Context Protocol (MCP), the AI decides *when* to search, update profiles, or create orders
- **[Fully async](#the-services--what-each-piece-does)** — eight FastAPI microservices, all I/O non-blocking

---

## Architecture

<div align="center">
  <img src="images/pipline.png" alt="Magic Sale AI Architecture" width="700" />
</div>

<br />

The orchestrator (`models-service`) does four things on every message:

1. **Asks `chat-service`** for conversation history — from a Redis cache backed by PostgreSQL
2. **Asks `prompt-service`** for a personalized system prompt — assembled from modular components per-user
3. **Connects to `mcp-service`** so the AI can call tools (search products, check inventory, create orders, send emails)
4. **Sends everything to the LLM** and returns the response to the customer via Zalo

---

## How It Works

```
Customer                    Magic Sale AI
   │
   │  "Chào shop!"
   ├──────────────────▶  Zalo webhook receives message
   │                          │
   │                          ▼
   │                    models-service (Orchestrator)
   │                          │
   │           ┌──────────────┼──────────────────┐
   │           │              │                   │
   │           ▼              ▼                   ▼
   │     chat-service   prompt-service       mcp-service
   │     "Conversation  "Who is this user?   "What tools does
   │      history —      What personality     the AI need right
   │      Redis+PG       should I use?"       now?"
   │           │              │                   │
   │           └──────────────┴──────────────┬────┘
   │                                         │
   │                                         ▼
   │                                   AI generates response
   │                                   (with the right tone,
   │                                    the right knowledge,
   │  "Dạ em recommend                  the right tools)
   │   Ensure Gold cho                       │
   │   ba anh/chị ạ! 😊"                    │
   │◀────────────────────────────────────────┘
```

---

## Key Concepts

### The Prompt Architecture — Why Every Conversation Feels Different

Most chatbots use one system prompt for everyone. Magic Sale AI builds a **unique prompt per customer** by combining six modular components at request time:

```
┌─────────────────────────────────────────────────────┐
│              system_prompt.md (Jinja2)               │
│                                                      │
│   ┌──────────┐  ┌──────────┐  ┌────────────────┐   │
│   │ IDENTITY │  │   SOUL   │  │      USER      │   │
│   │ "I am    │  │ Warm,    │  │ Nguyễn Văn A,  │   │
│   │  NutriBot│  │ empathic,│  │ 65 tuổi, tiểu  │   │
│   │  from    │  │ never    │  │ đường, thích   │   │
│   │  Abbott" │  │ pushy    │  │ Ensure Gold    │   │
│   └──────────┘  └──────────┘  └────────────────┘   │
│                                                      │
│   ┌──────────┐  ┌──────────┐  ┌────────────────┐   │
│   │  AGENTS  │  │  TOOLS   │  │     MEMORY     │   │
│   │ Safety   │  │ Which    │  │ "Last time,    │   │
│   │ rails &  │  │ MCP tools│  │  this customer │   │
│   │ behavior │  │ are on   │  │  was price-    │   │
│   │ rules    │  │ right now│  │  sensitive"    │   │
│   └──────────┘  └──────────┘  └────────────────┘   │
└─────────────────────────────────────────────────────┘
```

| Component | What it controls | Example |
|:----------|:-----------------|:--------|
| **IDENTITY** | Bot name, tone, character constraints | "Xưng *em*, gọi khách *anh/chị*" |
| **SOUL** | Emotional personality and empathy rules | "Hỏi trước, tư vấn sau — never dump product lists" |
| **USER** | Customer profile that evolves per interaction | Age, health notes, preferences, past objections |
| **AGENTS** | Behavioral guardrails and safety rules | "Don't search products until the Discovery phase" |
| **TOOLS** | Which MCP tools are available per phase | Search tools unlock only in Support phase |
| **MEMORY** | Long-term pattern recognition per customer | "This customer responds well to health-benefit framing" |

Each component is stored **per-user in PostgreSQL** and rendered via Jinja2 at request time. When a customer shares new info, the AI updates their profile in real-time using the `edit_personal_profile` tool.

---

### Skills — The AI's Sales Playbook

The AI's behavior is driven by a **skills system** — markdown resources loaded one phase at a time via the `read_skill_resource` tool:

```
models-service/skills/sales-conversion/
├── SKILL.md              # Skill manifest: phases, golden rules, execution constraints
└── resources/
    ├── 01-opening.md     # Phase 1: greet & build rapport
    ├── 02-discovery.md   # Phase 2: SPIN questions — who, age, health goals
    ├── 03-support.md     # Phase 3: recommend products, assumptive close
    ├── 04-objection-handling.md  # Phase 4: soothe → clarify → satisfy (max 3x)
    └── 05-closing.md     # Phase 5: collect order info, confirm, send email
```

**Key constraint**: only the resource for the current phase is loaded per turn. The AI never sees the full playbook at once — it reads ahead one step at a time, exactly like a real salesperson following a script.

---

### SPIN Selling — The Sales Methodology Inside the AI

```
 ┌───────────┐     ┌───────────┐     ┌───────────┐     ┌───────────┐     ┌───────────┐
 │  Opening  │────▶│ Discovery │────▶│  Support   │────▶│ Objection │────▶│  Closing  │
 │           │     │           │     │            │     │ Handling  │     │           │
 │ Greet &   │     │ Ask about │     │ Recommend  │     │ Soothe →  │     │ Collect   │
 │ build     │     │ who,what, │     │ products & │     │ Clarify → │     │ order     │
 │ rapport   │     │ health    │     │ explain    │     │ Satisfy   │     │ info &    │
 │           │     │ conditions│     │ benefits   │     │ (max 3x)  │     │ confirm   │
 └───────────┘     └───────────┘     └───────────┘     └───────────┘     └───────────┘
```

The AI tracks its phase using a state machine. It won't search for products during Opening. It won't try to close during Discovery. Each phase has its own conversational rules, tone, and available tools.

**Key rule**: The AI never says "Bạn có muốn mua không?" (Do you want to buy?). Instead, it uses **assumptive closing**: "Anh/chị lấy gói 850g hay 400g dùng thử ạ?" — guiding toward a choice, not a yes/no.

---

### MCP Tools — What the AI Can Actually Do

| Tool | When | What it does |
|:-----|:-----|:-------------|
| `search_keyword` | Support phase | Full-text product search across the catalog |
| `search_by_age` | Support phase | Age-appropriate product recommendations |
| `rag_search` | Support phase | Hybrid dense+sparse vector search (Qdrant + TEI reranker + MMR) |
| `view_personal_profile` | Any phase | Retrieve the customer's profile & preferences |
| `edit_personal_profile` | Any phase | Update customer info as they share it |
| `read_skill_resource` | Each turn | Load the active sales skill instruction for the current phase |
| `create_order` | Closing phase | Place an order with ACID inventory validation |
| `send_email` | Closing phase | Send order confirmation to the customer |

Search tools are **gated** — they only activate during the Support phase. During Opening and Discovery, the AI focuses purely on rapport and understanding needs.

---

### The Services — What Each Piece Does

| Service | What it does |
|:--------|:-------------|
| **zalo-service** | The front door. Receives Zalo messages via webhook or polling, forwards to the orchestrator |
| **models-service** | The brain. Runs the AgentScope ReActAgent, loads sales skills, manages MCP tool calls |
| **chat-service** | The memory buffer. Stores messages in PostgreSQL, serves from Redis ZSET cache — sub-5ms reads |
| **prompt-service** | The personality engine. Per-user prompt components in PostgreSQL, assembled via Jinja2 |
| **mcp-service** | The hands. All tools the AI can call — search, profile management, ordering, email |
| **rag-service** | The knowledge engine. Hybrid vector search over the catalog via Qdrant with RRF + MMR |
| **data-service** | The catalog. Product CRUD, CSV import, full-text search |
| **order-service** | The cash register. Order lifecycle with ACID inventory transactions |

Every service follows the same structure:

```
<service>/
├── main.py              # FastAPI entrypoint
├── requirements.txt     # Isolated dependencies
├── .env.example         # Environment template
└── app/
    ├── api/             # Route handlers
    ├── services/        # Business logic
    ├── repositories/    # Data access layer
    ├── db/              # SQLAlchemy models
    └── core/            # Config & logging
```

---

### Memory — Short-Term and Long-Term

- **Short-term** (`chat-service`): every message in PostgreSQL, cached in Redis ZSET. Sub-5ms when cached, ~20–50ms on miss.
- **Long-term** (PostgreSQL via `prompt-service`): customer profile — name, age, health conditions, preferred products, objection patterns — persists across conversations.

When a customer says "Ba em bị tiểu đường" (My dad has diabetes), the AI calls `edit_personal_profile` to save this. Days later, the AI already knows.

---

## Tech Stack

| Layer | Technology |
|:------|:-----------|
| **Language** | Python 3.11, async everywhere |
| **Framework** | FastAPI (8 microservices) |
| **AI Agent** | AgentScope (ReActAgent) + Model Context Protocol (MCP) |
| **LLM** | OpenAI-compatible API (GPT, Azure, any endpoint) |
| **Database** | PostgreSQL 16 with pgvector |
| **Cache** | Redis 7 (ZSET for chat history) |
| **Vector Search** | Qdrant + TEI Reranker + MMR |
| **Templating** | Jinja2 (per-user prompt assembly) |
| **Infra** | Docker Compose, Nginx, Alembic |
| **Channel** | Zalo OA Bot API |

[![Python][Python-shield]][Python-url]
[![FastAPI][FastAPI-shield]][FastAPI-url]
[![PostgreSQL][PostgreSQL-shield]][PostgreSQL-url]
[![Redis][Redis-shield]][Redis-url]
[![Docker][Docker-shield]][Docker-url]
[![Pydantic][Pydantic-shield]][Pydantic-url]
[![OpenAI][OpenAI-shield]][OpenAI-url]
[![Jinja2][Jinja2-shield]][Jinja2-url]
[![Nginx][Nginx-shield]][Nginx-url]

---

## Getting Started

### Prerequisites

- **Python 3.11+**
- **Docker & Docker Compose**
- **Zalo OA Bot Token** — [Zalo Developers](https://developers.zalo.me)
- **OpenAI-compatible API Key** — OpenAI, Azure OpenAI, or any compatible endpoint
- **Ollama** _(optional)_ — for local embeddings

### Docker (full stack)

```bash
git clone https://github.com/magic-sales/magic-sale-ai.git
cd magic-sale-ai/infrastructure

make setup       # copies .env, builds images, runs migrations, imports data
make up          # start all services
make health      # verify everything is running
```

### Local Development

```bash
git clone https://github.com/magic-sales/magic-sale-ai.git
cd magic-sale-ai

cd infrastructure && make dev-infra   # start only PostgreSQL + Redis
cd ..
./scripts/chat-up.sh                  # start all services locally
./scripts/chat-status.sh              # check status
./scripts/chat-down.sh                # stop everything
```

### Per-Service Development

```bash
cd models-service                     # or any service directory
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                  # edit with your API keys
uvicorn main:app --reload --port 8000
```

Service ports: `models=8000` · `prompt=8001` · `data=8002` · `order=8003` · `mcp=8004` · `zalo=8080`

---

## Useful Commands

```bash
# Infrastructure (from infrastructure/)
make up / down / build / logs / ps    # container lifecycle
make restart-mcp-service              # restart a specific service
make psql / redis-cli                 # connect to databases
make migrate                          # run all Alembic migrations
make import                           # import product CSV data
make health                           # health check all services

# Local scripts
./scripts/chat-up.sh                  # start all services locally
./scripts/chat-down.sh                # stop all services
./scripts/chat-status.sh              # check service status
./scripts/chat-logs.sh                # view aggregated logs
```

---

## Configuration

Each service reads from its own `.env` file. See each service's `.env.example` for the complete list:

| Service | Key variables |
|:--------|:-------------|
| **models-service** | `MODEL_NAME`, `API_KEY`, `BASE_URL`, `PROMPT_SERVICE_URL`, `MCP_SERVICE_URL`, `CHAT_SERVICE_URL` |
| **zalo-service** | `ZALO_BOT_TOKEN`, `MODEL_SERVICE_URL`, `WEBHOOK_SECRET_TOKEN` |
| **mcp-service** | `DATABASE_URL`, `ORDER_SERVICE_URL`, `SMTP_HOST`, `RAG_SERVICE_URL` |
| **chat-service** | `DATABASE_URL`, `REDIS_URL`, `CACHE_TTL`, `DEFAULT_TOP_K` |
| **rag-service** | `GEMINI_API_KEY`, `QDRANT_HOST`, `QDRANT_PORT`, `TEI_RERANKER_URL` |
| **Infrastructure** | `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `REDIS_PORT` |

---

## Roadmap

- [x] Multi-service microservice architecture (8 services)
- [x] AgentScope ReActAgent with MCP tool calling
- [x] Per-user adaptive prompt system
- [x] Skills-based sales playbook (sales-conversion skill)
- [x] RAG-powered hybrid search (Qdrant + TEI reranker + MMR)
- [x] Full order lifecycle with inventory management
- [x] Dedicated chat-service (Redis+PG conversation history)
- [x] Smart message pre-processing (health-answer detection, "wants-all" detection)
- [x] Context-aware intent classification with hidden hints
- [ ] Multi-language support (English, Vietnamese)
- [ ] Admin dashboard for analytics and monitoring
- [ ] A/B testing for prompt strategies
- [ ] Multi-channel support (Facebook Messenger, Telegram)
- [ ] Voice message processing

See the [open issues](https://github.com/magic-sales/magic-sale-ai/issues) for a full list.

---

## Contributing

Contributions are **greatly appreciated**. Fork the repo and create a pull request — or open an issue with the tag "enhancement".

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feat/amazing-feature`)
3. Commit your Changes (`git commit -m 'feat: add amazing feature'`)
4. Push to the Branch (`git push origin feat/amazing-feature`)
5. Open a Pull Request

We follow [Conventional Commits](https://www.conventionalcommits.org/) — use `feat:`, `fix:`, `chore:`, `docs:` prefixes.

<a href="https://github.com/magic-sales/magic-sale-ai/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=magic-sales/magic-sale-ai" alt="Contributors" />
</a>

---

## License

Distributed under the **GNU General Public License v3.0**. See `LICENSE` for more information.

## Contact

**Team Magic Sales** — [Project Link](https://github.com/magic-sales/magic-sale-ai)

## Acknowledgments

- [FastAPI](https://fastapi.tiangolo.com/) — High-performance async web framework
- [AgentScope](https://github.com/modelscope/agentscope) — Multi-agent framework with ReActAgent and MCP support
- [FastMCP](https://github.com/jlowin/fastmcp) — Model Context Protocol server
- [pgvector](https://github.com/pgvector/pgvector) — Vector similarity search for PostgreSQL
- [python-zalo-bot](https://pypi.org/project/python-zalo-bot/) — Zalo OA API client
- [Ollama](https://ollama.com/) — Local LLM and embedding inference

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- MARKDOWN LINKS & IMAGES -->
[contributors-shield]: https://img.shields.io/github/contributors/magic-sales/magic-sale-ai.svg?style=for-the-badge
[contributors-url]: https://github.com/magic-sales/magic-sale-ai/graphs/contributors
[forks-shield]: https://img.shields.io/github/forks/magic-sales/magic-sale-ai.svg?style=for-the-badge
[forks-url]: https://github.com/magic-sales/magic-sale-ai/network/members
[stars-shield]: https://img.shields.io/github/stars/magic-sales/magic-sale-ai.svg?style=for-the-badge
[stars-url]: https://github.com/magic-sales/magic-sale-ai/stargazers
[issues-shield]: https://img.shields.io/github/issues/magic-sales/magic-sale-ai.svg?style=for-the-badge
[issues-url]: https://github.com/magic-sales/magic-sale-ai/issues
[license-shield]: https://img.shields.io/github/license/magic-sales/magic-sale-ai.svg?style=for-the-badge
[license-url]: https://github.com/magic-sales/magic-sale-ai/blob/main/LICENSE

<!-- TECH STACK BADGES -->
[Python-shield]: https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white
[Python-url]: https://python.org
[FastAPI-shield]: https://img.shields.io/badge/FastAPI-0.115-009688?style=for-the-badge&logo=fastapi&logoColor=white
[FastAPI-url]: https://fastapi.tiangolo.com
[PostgreSQL-shield]: https://img.shields.io/badge/PostgreSQL-16-4169E1?style=for-the-badge&logo=postgresql&logoColor=white
[PostgreSQL-url]: https://postgresql.org
[Redis-shield]: https://img.shields.io/badge/Redis-7-DC382D?style=for-the-badge&logo=redis&logoColor=white
[Redis-url]: https://redis.io
[Docker-shield]: https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white
[Docker-url]: https://docker.com
[Pydantic-shield]: https://img.shields.io/badge/AgentScope-FF6B35?style=for-the-badge&logo=python&logoColor=white
[Pydantic-url]: https://github.com/modelscope/agentscope
[OpenAI-shield]: https://img.shields.io/badge/OpenAI_SDK-412991?style=for-the-badge&logo=openai&logoColor=white
[OpenAI-url]: https://platform.openai.com
[Jinja2-shield]: https://img.shields.io/badge/Jinja2-B41717?style=for-the-badge&logo=jinja&logoColor=white
[Jinja2-url]: https://jinja.palletsprojects.com
[Nginx-shield]: https://img.shields.io/badge/Nginx-009639?style=for-the-badge&logo=nginx&logoColor=white
[Nginx-url]: https://nginx.org
