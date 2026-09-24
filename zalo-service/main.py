"""
zalo-service entry point.

Modes:
  webhook (default / production):
      FastAPI app listens for POST /webhook from Zalo Platform.
      Requires a public HTTPS URL (ngrok / Cloudflare Tunnel for dev).

  polling (development / local):
      Polls Zalo OA API every 2 s.  No public URL required.

Usage:
    python main.py                          # webhook, 0.0.0.0:8080
    python main.py --mode webhook --port 8080
    python main.py --mode polling
"""

import argparse
import asyncio

import uvicorn
from fastapi import FastAPI

from app.api.webhook import router
from app.core.logger import get_logger

logger = get_logger("main")

# ---------------------------------------------------------------------------
# FastAPI application (used in webhook mode and importable for tests)
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Zalo Service",
    description="Zalo OA webhook gateway for Magic Sale AI",
    version="1.0.0",
)

app.include_router(router)


@app.on_event("startup")
async def _on_startup() -> None:
    logger.info("zalo_service_started", extra={"mode": "webhook"})


@app.on_event("shutdown")
async def _on_shutdown() -> None:
    logger.info("zalo_service_stopped")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Magic Sale AI — Zalo Service",
    )
    parser.add_argument(
        "--mode",
        choices=["webhook", "polling"],
        default="webhook",
        help="webhook = production HTTP server; polling = dev poll loop",
    )
    parser.add_argument("--host", default="0.0.0.0", help="Bind host (webhook mode)")
    parser.add_argument(
        "--port", type=int, default=8080, help="Bind port (webhook mode)"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    if args.mode == "polling":
        logger.info("zalo_service_started", extra={"mode": "polling"})
        from app.runtime.polling import run_polling

        async def _run_polling_with_http() -> None:
            """Run polling loop + FastAPI HTTP server concurrently."""
            config = uvicorn.Config(
                "main:app", host=args.host, port=args.port,
                log_level="warning",
            )
            server = uvicorn.Server(config)
            await asyncio.gather(
                server.serve(),
                run_polling(),
            )

        asyncio.run(_run_polling_with_http())
    else:
        # Webhook mode — run FastAPI via uvicorn
        uvicorn.run(
            "main:app",
            host=args.host,
            port=args.port,
            log_level="warning",   # uvicorn's own logs; our logger handles the rest
            reload=False,
        )
