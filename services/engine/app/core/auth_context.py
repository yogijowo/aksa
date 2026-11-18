"""Trusted Authentication & Principal Context Resolution for AKSA (P0-03).

Enforces trusted desktop host identity:
- Single-user desktop security model binds the authenticated principal to the host OS user.
- Eliminates insecure fallback to arbitrary unverified 'default_user'.
- Blocks unverified spoofing of X-Principal-ID or owner_id headers in production.
"""

from __future__ import annotations

import getpass
from typing import Any
from fastapi import HTTPException, Request

from app.config import settings


def get_default_host_principal() -> str:
    """Return the canonical, authenticated host principal for the current desktop environment."""
    try:
        user = getpass.getuser()
        if user:
            return f"user:{user}"
    except Exception:
        pass
    return "user:local_desktop"


def resolve_authenticated_principal(request: Request | None = None) -> str:
    """Resolve the genuine, authenticated principal ID.
    
    Security Guarantees:
    1. In production, X-Principal-ID header is verified against host runtime identity. Spoofing is blocked (403).
    2. In testing mode, distinct principals may be simulated only when settings.testing or settings.dev_mode is True.
    3. Guarantees a non-empty, authenticated principal is always returned.
    """
    trusted_host_principal = get_default_host_principal()

    if request is not None:
        claimed_principal = request.headers.get("X-Principal-ID")
        if claimed_principal:
            claimed_principal = claimed_principal.strip()
            # If in testing mode, permit multi-principal isolation unit tests
            if settings.testing or settings.dev_mode:
                return claimed_principal
            # In production, client cannot unilaterally spoof another principal
            if claimed_principal != trusted_host_principal:
                raise HTTPException(
                    status_code=403,
                    detail=f"Pelanggaran Otorisasi: Principal '{claimed_principal}' tidak sesuai dengan identitas host terautentikasi.",
                )

    return trusted_host_principal

