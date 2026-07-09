"""
OmniCore — Utilities
Shared helpers: API response formatting, pagination, validation, and security.
"""
import re
import time
import hashlib
import secrets
import string
from datetime import datetime
from typing import Any, Optional

from fastapi import HTTPException, status


# ── API Response Builder ──────────────────────────────────────────────────────

def success_response(
    data: Any = None,
    message: str = "Success",
    count: Optional[int] = None,
    page: Optional[int] = None,
    total: Optional[int] = None,
    execution_time_ms: Optional[int] = None,
) -> dict:
    """
    Build a consistent success response envelope.
    All OmniCore API responses share this structure.
    """
    response = {
        "success": True,
        "message": message,
        "execution_time_ms": execution_time_ms,
    }
    if total is not None:
        response["total"] = total
    if count is not None:
        response["count"] = count
    if page is not None:
        response["page"] = page
    if data is not None:
        response["data"] = data
    return response


def error_response(message: str, detail: Optional[str] = None) -> dict:
    """Build a consistent error response envelope."""
    resp = {"success": False, "message": message}
    if detail:
        resp["detail"] = detail
    return resp


class Timer:
    """Context manager that measures execution time in milliseconds."""

    def __init__(self):
        self.elapsed_ms: int = 0
        self._start: float = 0.0

    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, *_):
        self.elapsed_ms = int((time.perf_counter() - self._start) * 1000)


# ── Validation ────────────────────────────────────────────────────────────────

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")
USERNAME_REGEX = re.compile(r"^[a-zA-Z0-9_]{3,32}$")


def validate_email(email: str) -> str:
    """Validate and normalise an email address."""
    email = email.strip().lower()
    if not EMAIL_REGEX.match(email):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid email address.",
        )
    return email


def validate_username(username: str) -> str:
    """Validate a username (3–32 chars, alphanumeric + underscore)."""
    username = username.strip()
    if not USERNAME_REGEX.match(username):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Username must be 3–32 characters and contain only letters, numbers, and underscores.",
        )
    return username


def validate_password(password: str) -> None:
    """
    Enforce password complexity rules.
    Minimum 8 characters, at least one uppercase, one lowercase,
    one digit, and one special character.
    """
    if len(password) < 8:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must be at least 8 characters long.",
        )
    if not re.search(r"[A-Z]", password):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must contain at least one uppercase letter.",
        )
    if not re.search(r"[a-z]", password):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must contain at least one lowercase letter.",
        )
    if not re.search(r"\d", password):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must contain at least one digit.",
        )
    if not re.search(r"[^A-Za-z0-9]", password):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must contain at least one special character.",
        )


# ── API Key Generation ────────────────────────────────────────────────────────

def generate_api_key() -> tuple[str, str, str]:
    """
    Generate a secure API key.

    Returns:
        (raw_key, key_hash, key_prefix)
        - raw_key: shown to the user once, never stored
        - key_hash: SHA-256 hash stored in the database
        - key_prefix: first 12 chars used for display (e.g. omni_abc12345)
    """
    alphabet = string.ascii_letters + string.digits
    random_part = "".join(secrets.choice(alphabet) for _ in range(40))
    raw_key = f"omni_{random_part}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    key_prefix = raw_key[:12]
    return raw_key, key_hash, key_prefix


def hash_api_key(raw_key: str) -> str:
    """Hash an API key for secure database storage."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


# ── Pagination ────────────────────────────────────────────────────────────────

def paginate(page: int = 1, page_size: int = 20) -> tuple[int, int]:
    """
    Validate and return (offset, limit) for a paginated query.
    page is 1-indexed.
    """
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    offset = (page - 1) * page_size
    return offset, page_size


# ── String Utilities ──────────────────────────────────────────────────────────

def slugify(text: str) -> str:
    """Convert a string to a URL-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    text = re.sub(r"^-+|-+$", "", text)
    return text


def format_bytes(num_bytes: Optional[int]) -> str:
    """Format bytes into a human-readable string."""
    if num_bytes is None:
        return "Unknown"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num_bytes < 1024:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} PB"


def utcnow_iso() -> str:
    """Return current UTC time as an ISO-8601 string."""
    return datetime.utcnow().isoformat() + "Z"
