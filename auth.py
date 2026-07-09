"""
OmniCore — Authentication
JWT-based authentication with Argon2id password hashing.
Includes routes, middleware, and token management.

Architecture is designed for future SuperTokens migration:
  - Auth logic is isolated to this module
  - Token validation is middleware-injectable
  - No auth state leaks into business logic
"""
import hashlib
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from models import APIKey, RefreshToken, User
from utils import (
    Timer,
    generate_api_key,
    success_response,
    validate_email,
    validate_password,
    validate_username,
)

# ── Password Hashing ──────────────────────────────────────────────────────────
# Prefer Argon2id; fall back to bcrypt if argon2-cffi is unavailable.

try:
    from argon2 import PasswordHasher
    from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError

    _ph = PasswordHasher(
        time_cost=2,
        memory_cost=65536,  # 64 MB
        parallelism=2,
        hash_len=32,
        salt_len=16,
    )

    def hash_password(plain: str) -> str:
        return _ph.hash(plain)

    def verify_password(plain: str, hashed: str) -> bool:
        try:
            return _ph.verify(hashed, plain)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False

    PASSWORD_BACKEND = "argon2id"

except ImportError:
    import bcrypt

    def hash_password(plain: str) -> str:  # type: ignore[misc]
        return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=12)).decode()

    def verify_password(plain: str, hashed: str) -> bool:  # type: ignore[misc]
        try:
            return bcrypt.checkpw(plain.encode(), hashed.encode())
        except Exception:
            return False

    PASSWORD_BACKEND = "bcrypt"


# ── JWT Helpers ───────────────────────────────────────────────────────────────

def _create_token(data: dict, expires_delta: timedelta) -> str:
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + expires_delta
    payload["iat"] = datetime.utcnow()
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_access_token(user_id: str, email: str) -> str:
    return _create_token(
        {"sub": user_id, "email": email, "type": "access"},
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(user_id: str) -> str:
    return _create_token(
        {"sub": user_id, "type": "refresh"},
        timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


def decode_token(token: str) -> dict:
    """Decode and validate a JWT. Raises HTTPException on failure."""
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


def _hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


# ── Bearer Security Scheme ────────────────────────────────────────────────────

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """
    FastAPI dependency — resolves the authenticated user from a Bearer JWT.
    Works with both JWT access tokens AND raw OmniCore API keys.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    # Try API key first (starts with "omni_")
    if token.startswith("omni_"):
        key_hash = hashlib.sha256(token.encode()).hexdigest()
        api_key = db.query(APIKey).filter_by(key_hash=key_hash, is_active=True).first()
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key.",
            )
        api_key.last_used = datetime.utcnow()
        api_key.usage_count += 1
        db.commit()
        user = db.query(User).filter_by(id=api_key.user_id, is_active=True).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is inactive.",
            )
        return user

    # Fall back to JWT
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token required.",
        )
    user = db.query(User).filter_by(id=payload["sub"], is_active=True).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found.",
        )
    return user


def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Like get_current_user but returns None instead of raising for unauthenticated requests."""
    if not credentials:
        return None
    try:
        return get_current_user(credentials, db)
    except HTTPException:
        return None


# ── Pydantic Schemas ──────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: str
    username: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class CreateAPIKeyRequest(BaseModel):
    name: str = "Default Key"


# ── Router ────────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register")
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    """Register a new developer account."""
    with Timer() as t:
        email = validate_email(body.email)
        username = validate_username(body.username)
        validate_password(body.password)

        if db.query(User).filter_by(email=email).first():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists.",
            )
        if db.query(User).filter_by(username=username).first():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username is already taken.",
            )

        user = User(
            email=email,
            username=username,
            password_hash=hash_password(body.password),
        )
        db.add(user)
        db.flush()

        # Generate one universal API key on registration
        raw_key, key_hash, key_prefix = generate_api_key()
        api_key = APIKey(
            user_id=user.id,
            key_hash=key_hash,
            key_prefix=key_prefix,
            name="Default Key",
        )
        db.add(api_key)
        db.commit()

        access_token = create_access_token(user.id, user.email)
        refresh_raw = create_refresh_token(user.id)

        rt = RefreshToken(
            user_id=user.id,
            token_hash=_hash_refresh_token(refresh_raw),
            expires_at=datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
        db.add(rt)
        db.commit()

    return success_response(
        data={
            "user": {
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "created_at": user.created_at.isoformat() + "Z",
            },
            "access_token": access_token,
            "refresh_token": refresh_raw,
            "token_type": "bearer",
            "api_key": raw_key,   # shown once — never stored in plaintext
            "api_key_prefix": key_prefix,
            "password_backend": PASSWORD_BACKEND,
        },
        message="Account created successfully.",
        execution_time_ms=t.elapsed_ms,
    )


@router.post("/login")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate with email and password, return JWT pair."""
    with Timer() as t:
        email = validate_email(body.email)
        user = db.query(User).filter_by(email=email, is_active=True).first()

        if not user or not verify_password(body.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
            )

        user.last_login = datetime.utcnow()
        db.commit()

        access_token = create_access_token(user.id, user.email)
        refresh_raw = create_refresh_token(user.id)

        rt = RefreshToken(
            user_id=user.id,
            token_hash=_hash_refresh_token(refresh_raw),
            expires_at=datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
        db.add(rt)
        db.commit()

    return success_response(
        data={
            "user": {
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "last_login": user.last_login.isoformat() + "Z" if user.last_login else None,
            },
            "access_token": access_token,
            "refresh_token": refresh_raw,
            "token_type": "bearer",
        },
        message="Login successful.",
        execution_time_ms=t.elapsed_ms,
    )


@router.post("/refresh")
def refresh_token(body: RefreshRequest, db: Session = Depends(get_db)):
    """Exchange a valid refresh token for a new access token."""
    with Timer() as t:
        payload = decode_token(body.refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token required.",
            )

        token_hash = _hash_refresh_token(body.refresh_token)
        rt = db.query(RefreshToken).filter_by(token_hash=token_hash, revoked=False).first()

        if not rt or rt.expires_at < datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token is invalid or expired.",
            )

        user = db.query(User).filter_by(id=rt.user_id, is_active=True).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found.",
            )

        # Rotate refresh token
        rt.revoked = True
        rt.revoked_at = datetime.utcnow()

        new_refresh_raw = create_refresh_token(user.id)
        new_rt = RefreshToken(
            user_id=user.id,
            token_hash=_hash_refresh_token(new_refresh_raw),
            expires_at=datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
        db.add(new_rt)
        db.commit()

        new_access = create_access_token(user.id, user.email)

    return success_response(
        data={
            "access_token": new_access,
            "refresh_token": new_refresh_raw,
            "token_type": "bearer",
        },
        message="Token refreshed.",
        execution_time_ms=t.elapsed_ms,
    )


@router.post("/logout")
def logout(
    body: RefreshRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revoke the provided refresh token."""
    token_hash = _hash_refresh_token(body.refresh_token)
    rt = db.query(RefreshToken).filter_by(
        token_hash=token_hash, user_id=current_user.id, revoked=False
    ).first()
    if rt:
        rt.revoked = True
        rt.revoked_at = datetime.utcnow()
        db.commit()
    return success_response(message="Logged out successfully.")


@router.get("/me")
def get_me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Return the authenticated user's profile."""
    api_keys = (
        db.query(APIKey)
        .filter_by(user_id=current_user.id, is_active=True)
        .order_by(APIKey.created_at.desc())
        .all()
    )
    return success_response(
        data={
            "id": current_user.id,
            "email": current_user.email,
            "username": current_user.username,
            "is_active": current_user.is_active,
            "created_at": current_user.created_at.isoformat() + "Z",
            "last_login": current_user.last_login.isoformat() + "Z" if current_user.last_login else None,
            "api_keys": [
                {
                    "id": k.id,
                    "name": k.name,
                    "key_prefix": k.key_prefix,
                    "usage_count": k.usage_count,
                    "last_used": k.last_used.isoformat() + "Z" if k.last_used else None,
                    "created_at": k.created_at.isoformat() + "Z",
                }
                for k in api_keys
            ],
        }
    )


@router.post("/api-keys")
def create_api_key(
    body: CreateAPIKeyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate a new API key for the authenticated user."""
    # Enforce a reasonable per-user limit
    existing = db.query(APIKey).filter_by(user_id=current_user.id, is_active=True).count()
    if existing >= 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum of 5 active API keys allowed. Revoke an existing key first.",
        )

    raw_key, key_hash, key_prefix = generate_api_key()
    api_key = APIKey(
        user_id=current_user.id,
        key_hash=key_hash,
        key_prefix=key_prefix,
        name=body.name[:100],
    )
    db.add(api_key)
    db.commit()

    return success_response(
        data={
            "id": api_key.id,
            "name": api_key.name,
            "api_key": raw_key,         # shown once — never stored
            "key_prefix": key_prefix,
            "created_at": api_key.created_at.isoformat() + "Z",
        },
        message="API key generated. Copy it now — it will not be shown again.",
    )


@router.delete("/api-keys/{key_id}")
def revoke_api_key(
    key_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revoke (deactivate) an API key belonging to the current user."""
    api_key = db.query(APIKey).filter_by(id=key_id, user_id=current_user.id).first()
    if not api_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found.")
    api_key.is_active = False
    db.commit()
    return success_response(message="API key revoked successfully.")
