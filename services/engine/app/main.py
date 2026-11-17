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


ALLOWED_ORIGINS = [
    "http://localhost:1420",
    "http://127.0.0.1:1420",
    "tauri://localhost",
    "http://tauri.localhost",
    "https://tauri.localhost",
]

ALLOWED_HOSTS = {"127.0.0.1", "localhost", "::1", "[::1]", "test", "testserver"}
MAX_REQUEST_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


def create_app() -> FastAPI:
    app = FastAPI(
        title="AKSA Core Sidecar Engine",
        description="Local Autonomous Multi-Agent, RAG, Office Automation & Telegram Engine",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-AKSA-Auth-Token", "X-Request-ID"],
    )

    @app.middleware("http")
    async def verify_security_and_auth(request: Request, call_next):
        # 1. Host header validation (DNS rebinding protection)
        host_header = request.headers.get("host", "127.0.0.1").split(":")[0].strip().lower()
        if host_header and host_header not in ALLOWED_HOSTS:
            return JSONResponse(
                status_code=403,
                content={
                    "code": "FORBIDDEN_HOST",
                    "detail": f"Host '{host_header}' ditolak. Local API hanya menerima koneksi loopback.",
                },
            )

        # 2. Origin header validation
        origin = request.headers.get("origin")
        if origin and origin not in ALLOWED_ORIGINS and not origin.startswith("http://test"):
            return JSONResponse(
                status_code=403,
                content={
                    "code": "FORBIDDEN_ORIGIN",
                    "detail": f"Origin '{origin}' tidak termasuk dalam daftar izin aplikasi AKSA.",
                },
            )

        # 3. Request payload size limit
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > MAX_REQUEST_SIZE_BYTES:
                    return JSONResponse(
                        status_code=413,
                        content={
                            "code": "PAYLOAD_TOO_LARGE",
                            "detail": "Ukuran request melebihi batas maksimum 10 MB.",
                        },
                    )
            except ValueError:
                pass

        if request.method == "OPTIONS" or request.url.path in ("/api/v1/health", "/docs", "/openapi.json"):
            return await call_next(request)

        # 4. Token authentication
        if not settings.dev_mode:
            raw_auth = request.headers.get("Authorization", "")
            bearer_token = raw_auth.split(" ", 1)[1].strip() if raw_auth.startswith("Bearer ") else ""
            token = request.headers.get("X-AKSA-Auth-Token") or bearer_token
            if not token or token != settings.auth_token:
                return JSONResponse(
                    status_code=401,
                    content={
                        "code": "UNAUTHORIZED_SIDECAR_TOKEN",
                        "detail": "Token autentikasi sidecar AKSA tidak valid.",
                    },
                )
        return await call_next(request)

    app.include_router(api_router)
    app.include_router(ws_router)
    return app


app = create_app()


def main() -> None:
    parser = argparse.ArgumentParser(description="AKSA Python FastAPI Sidecar Engine")
    parser.add_argument("--host", default="127.0.0.1", help="Bind loopback host address")
    parser.add_argument("--port", type=int, default=43120, help="Bind localhost port")
    parser.add_argument("--auth-token", default="dev-aksa-local-token", help="Per-session security token")
    parser.add_argument("--production", action="store_true", help="Enforce strict token authentication")
    args = parser.parse_args()

    if args.host not in ("127.0.0.1", "::1", "localhost"):
        raise ValueError(f"Pelanggaran Keamanan: Sidecar hanya boleh bind ke loopback, bukan '{args.host}'.")

    settings.host = args.host
    settings.port = args.port
    settings.auth_token = args.auth_token
    settings.dev_mode = not args.production

    uvicorn.run(app, host=settings.host, port=settings.port, log_level="info")


if __name__ == "__main__":
    main()

