"""FastAPI entrypoint for the AKSA Python Sidecar Engine."""

from __future__ import annotations

import argparse
from contextlib import asynccontextmanager
from typing import AsyncIterator

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import api_router
from app.api.ws import ws_router
from app.config import settings
from app.db.models import db_manager
from app.db.seed import seed_default_indonesian_team


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Initialize AppData directories, SQLite schema, and default Indonesian agent team on startup."""
    settings.ensure_directories()
    await db_manager.initialize()
    await seed_default_indonesian_team(db_manager)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="AKSA Core Sidecar Engine",
        description="Local Autonomous Multi-Agent, RAG, Office Automation & Telegram Engine",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def verify_auth_token(request: Request, call_next):
        if request.method == "OPTIONS" or request.url.path in ("/api/v1/health", "/docs", "/openapi.json"):
            return await call_next(request)
        if not settings.dev_mode:
            token = request.headers.get("X-AKSA-Auth-Token")
            if token != settings.auth_token:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Token autentikasi sidecar AKSA tidak valid."},
                )
        return await call_next(request)

    app.include_router(api_router)
    app.include_router(ws_router)
    return app


app = create_app()


def main() -> None:
    parser = argparse.ArgumentParser(description="AKSA Python FastAPI Sidecar Engine")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host address")
    parser.add_argument("--port", type=int, default=43120, help="Bind localhost port")
    parser.add_argument("--auth-token", default="dev-aksa-local-token", help="Per-session security token")
    parser.add_argument("--production", action="store_true", help="Enforce strict token authentication")
    args = parser.parse_args()

    settings.host = args.host
    settings.port = args.port
    settings.auth_token = args.auth_token
    settings.dev_mode = not args.production

    uvicorn.run(app, host=settings.host, port=settings.port, log_level="info")


if __name__ == "__main__":
    main()

