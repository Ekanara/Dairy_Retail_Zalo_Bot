# Repository Guidelines

## Project Structure & Module Organization
This repository is a Python multi-service workspace. Main services live in top-level folders:
- `data-service/`, `order-service/`, `prompt-service/`, `models-service/`, `mcp-service/`, `zalo-service/`
- Each service follows a similar layout: `app/` (source), `docs/` (service docs), `main.py` (entrypoint), and optional `migrations/` + `alembic.ini`.
- Legacy prototypes and ad-hoc tests are under `trash/` (for example `trash/tests/`).
- Shared high-level docs are in [`README.md`](/home/chaos/Documents/chaos/magic-sale-ai/README.md).

## Build, Test, and Development Commands
Use a virtualenv per service.

```bash
cd prompt-service
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8001
```

Common run commands:
- `uvicorn main:app --reload --port 8000` (models-service)
- `python main.py --mode polling` (zalo-service local polling mode)
- `python main.py` (mcp-service)

Database services with Alembic:
- `alembic upgrade head` to apply migrations (run inside service folder).

## Coding Style & Naming Conventions
- Follow existing Python style: 4-space indentation, type hints, and `snake_case` for modules/functions/variables.
- Keep service boundaries clear: API routes in `app/api`, business logic in `app/services`, DB access in `app/repositories` or `app/db`.
- Prefer structured logging via each service’s `app/core/logger.py`; avoid `print()`.
- No global formatter config is committed yet; keep imports and naming consistent with surrounding files.

## Testing Guidelines
- Current tests are primarily `unittest`-based (`trash/tests/test_*.py`).
- Run all discovered tests from repo root:
  - `python -m unittest discover -s trash/tests -p 'test_*.py'`
- Add tests for new behavior, especially service/business logic and schema validation.
- Keep test file names as `test_<feature>.py`.

## Commit & Pull Request Guidelines
- History includes prefixes like `feat:`, `chore:`, and `update`; prefer Conventional Commit style (`feat:`, `fix:`, `chore:`) with concise subjects.
- Keep commits focused by service (for example, avoid mixing `data-service` and `models-service` refactors in one commit).
- PRs should include:
  - What changed and why
  - Services affected
  - Local verification steps/commands
  - Sample request/response or screenshots for API behavior changes
