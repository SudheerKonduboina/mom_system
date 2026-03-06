# app/auth_middleware.py
# API key authentication, rate limiting, and input validation

import os
import time
from collections import defaultdict
from functools import wraps

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings

# ---------------------------------------------------------------------------
# Rate Limiter (in-memory, per-IP)
# ---------------------------------------------------------------------------
_rate_store: dict = defaultdict(list)  # ip -> [timestamps]


def _check_rate_limit(ip: str, max_per_min: int) -> bool:
    now = time.time()
    window_start = now - 60
    _rate_store[ip] = [t for t in _rate_store[ip] if t > window_start]
    if len(_rate_store[ip]) >= max_per_min:
        return False
    _rate_store[ip].append(now)
    return True


# ---------------------------------------------------------------------------
# Auth Middleware
# ---------------------------------------------------------------------------
ALLOWED_EXTENSIONS = {".webm", ".wav", ".mp3", ".ogg", ".m4a", ".flac"}
PUBLIC_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Public endpoints — no auth needed
        if path in PUBLIC_PATHS or path.startswith("/storage"):
            return await call_next(request)

        # Rate limiting
        client_ip = request.client.host if request.client else "unknown"
        if not _check_rate_limit(client_ip, settings.RATE_LIMIT_PER_MIN):
            raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again later.")

        # API key authentication (only if API_SECRET_KEY is configured)
        if settings.API_SECRET_KEY:
            api_key = request.headers.get("X-API-Key", "")
            if api_key != settings.API_SECRET_KEY:
                raise HTTPException(status_code=401, detail="Invalid or missing API key.")

        response = await call_next(request)
        return response


# ---------------------------------------------------------------------------
# File Validation Helper
# ---------------------------------------------------------------------------
def validate_upload(filename: str, file_size: int = 0) -> list:
    """Validate uploaded file. Returns list of error messages (empty = valid)."""
    errors = []

    if not filename:
        errors.append("No filename provided.")
        return errors

    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        errors.append(f"File type '{ext}' not allowed. Accepted: {', '.join(ALLOWED_EXTENSIONS)}")

    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    if file_size > max_bytes:
        errors.append(f"File too large ({file_size // (1024*1024)}MB). Max: {settings.MAX_UPLOAD_MB}MB")

    return errors
