"""FastAPI entrypoint for the AKSA Python Sidecar Engine."""

from __future__ import annotations

import argparse
from contextlib import asynccontextmanager
import os
import secrets
import sys
from typing import AsyncIterator

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import api_router
from app.api.ws import ws_router
from app.config import settings
from app.core.observability import observability_manager
from app.core.privacy_gate import privacy_policy_gate
from app.db.models import db_manager
from app.db.seed import seed_default_indonesian_team


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Initialize AppData directories, SQLite schema, default Indonesian agent team, and persistent privacy policy."""
    settings.ensure_directories()
    await db_manager.initialize()
    await seed_default_indonesian_team(db_manager)
    await privacy_policy_gate.ensure_loaded_from_db(db_manager)

    # Write atomic runtime port file (AKSA-SEC-004-R2)
    port_file = settings.runtime_dir / "engine_port.json"
    runtime_info = {
        "host": settings.host,
        "port": settings.port,
        "pid": os.getpid(),
        "version": "1.0.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        import json
        temp_port_file = settings.runtime_dir / f"engine_port.json.tmp.{os.getpid()}"
        temp_port_file.write_text(json.dumps(runtime_info, indent=2), encoding="utf-8")
        os.replace(temp_port_file, port_file)
        sys.stderr.write(f"[AKSA_ENGINE_READY:port={settings.port}:pid={os.getpid()}]\n")
        sys.stderr.flush()
    except Exception:
        pass

    yield

    # Clean up port file on graceful shutdown
    try:
        if port_file.exists():
            port_file.unlink(missing_ok=True)
    except Exception:
        pass


def get_allowed_origins() -> list[str]:
    """Resolve strictly authorized CORS origins. Test origins only permitted in test/dev mode."""
    origins = [
        "http://localhost:1420",
        "http://127.0.0.1:1420",
        "tauri://localhost",
        "http://tauri.localhost",
        "https://tauri.localhost",
    ]
    if settings.testing or settings.dev_mode:
        origins.extend(["http://test", "http://testserver"])
    return origins


def get_allowed_hosts() -> set[str]:
    """Resolve strictly authorized Host headers to prevent DNS rebinding attacks."""
    hosts = {"127.0.0.1", "localhost", "::1", "[::1]"}
    if settings.testing or settings.dev_mode:
        hosts.update({"test", "testserver"})
    return hosts


MAX_REQUEST_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


def create_app() -> FastAPI:
    app = FastAPI(
        title="AKSA Core Sidecar Engine",
        description="Local Autonomous Multi-Agent, RAG, Office Automation & Telegram Engine",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.dev_mode else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.dev_mode else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_allowed_origins(),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-AKSA-Auth-Token", "X-Request-ID"],
    )

    @app.middleware("http")
    async def verify_security_and_auth(request: Request, call_next):
        # 1. Host header validation (DNS rebinding protection)
        host_header = request.headers.get("host", "127.0.0.1").split(":")[0].strip().lower()
        allowed_hosts = get_allowed_hosts()
        if host_header and host_header not in allowed_hosts:
            return JSONResponse(
                status_code=403,
                content={
                    "code": "FORBIDDEN_HOST",
                    "detail": f"Host '{host_header}' ditolak. Local API hanya menerima koneksi loopback.",
                },
            )

        # 2. Origin header validation
        origin = request.headers.get("origin")
        allowed_origins = get_allowed_origins()
        if origin and origin not in allowed_origins:
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

        if request.method == "OPTIONS" or request.url.path == "/api/v1/health":
            return await call_next(request)

        # 4. Token authentication (constant-time comparison)
        if not settings.dev_mode:
            raw_auth = request.headers.get("Authorization", "")
            bearer_token = raw_auth.split(" ", 1)[1].strip() if raw_auth.startswith("Bearer ") else ""
            token = request.headers.get("X-AKSA-Auth-Token") or bearer_token
            if not token or not secrets.compare_digest(token, settings.auth_token):
                return JSONResponse(
                    status_code=401,
                    content={
                        "code": "UNAUTHORIZED_SIDECAR_TOKEN",
                        "detail": "Token autentikasi sidecar AKSA tidak valid.",
                    },
                )
        return await call_next(request)

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": f"HTTP_{exc.status_code}",
                "detail": str(exc.detail),
            },
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        req_id = request.headers.get("X-Request-ID") or f"req_{secrets.token_hex(4)}"
        observability_manager.record_event(
            event_type="UNHANDLED_EXCEPTION",
            severity="ERROR",
            details={"path": str(request.url.path), "request_id": req_id, "error": str(exc)},
        )
        return JSONResponse(
            status_code=500,
            content={
                "code": "INTERNAL_SERVER_ERROR",
                "detail": "Terjadi kesalahan internal pada sistem AKSA. Silakan coba beberapa saat lagi.",
                "request_id": req_id,
            },
        )

    app.include_router(api_router)
    app.include_router(ws_router)
    return app


app = create_app()


def main() -> None:
    parser = argparse.ArgumentParser(description="AKSA Python FastAPI Sidecar Engine")
    parser.add_argument("--host", default="127.0.0.1", help="Bind loopback host address")
    parser.add_argument("--port", type=int, default=43120, help="Bind localhost port")
    parser.add_argument("--auth-token", default=None, help="Per-session security token")
    parser.add_argument("--dev", action="store_true", help="Run in local development mode (requires AKSA_DEV_MODE=1)")
    parser.add_argument("--production", action="store_true", help="Explicitly enforce production mode")
    parser.add_argument("--version", action="store_true", help="Print AKSA sidecar engine version and exit")
    parser.add_argument("--smoke-test", action="store_true", help="Run internal subsystems health verification and exit")
    args = parser.parse_args()

    if args.version:
        print("AKSA Engine v1.0.0 (API v1)")
        sys.exit(0)

    if args.smoke_test:
        import asyncio

        async def _run_smoke() -> None:
            settings.ensure_directories()
            await db_manager.initialize()
            await seed_default_indonesian_team(db_manager)
            await privacy_policy_gate.ensure_loaded_from_db(db_manager)
            print("[SMOKE-TEST] All sidecar engine subsystems initialized and verified successfully.")

        asyncio.run(_run_smoke())
        sys.exit(0)

    if args.host not in ("127.0.0.1", "::1", "localhost"):
        raise ValueError(f"Pelanggaran Keamanan: Sidecar hanya boleh bind ke loopback, bukan '{args.host}'.")

    # Invert default: production mode is default. Dev mode requires explicit --dev AND AKSA_DEV_MODE=1 (P0-3)
    is_explicit_dev = args.dev and (os.environ.get("AKSA_DEV_MODE", "").lower() in ("1", "true", "yes"))
    settings.dev_mode = is_explicit_dev and not args.production

    resolved_token = args.auth_token or os.environ.get("AKSA_AUTH_TOKEN", "").strip()
    if not settings.dev_mode:
        if not resolved_token or resolved_token == "dev-aksa-local-token":
            sys.stderr.write(
                "FATAL: AKSA Engine tidak dapat dijalankan dalam mode produksi tanpa token autentikasi valid.\n"
                "Sediakan token aman melalui environment variable AKSA_AUTH_TOKEN atau argumen --auth-token,\n"
                "atau gunakan flag --dev bersama AKSA_DEV_MODE=1 untuk mode pengembangan lokal.\n"
            )
            sys.exit(1)
        settings.auth_token = resolved_token
    else:
        settings.auth_token = resolved_token or "dev-aksa-local-token"
        sys.stderr.write(
            "\n"
            "*******************************************************************************\n"
            "* PERINGATAN KEAMANAN: AKSA ENGINE BERJALAN DALAM MODE PENGEMBANGAN (DEV_MODE)  *\n"
            "* JANGAN DIGUNAKAN DI LINGKUNGAN PRODUKSI. AUTENTIKASI LOKAL AKTIF.           *\n"
            "*******************************************************************************\n\n"
        )

    settings.host = args.host
    settings.port = args.port

    uvicorn.run(app, host=settings.host, port=settings.port, log_level="info")


if __name__ == "__main__":
    main()

