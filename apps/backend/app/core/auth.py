import time
from typing import Any

import httpx
import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer
from jwt import PyJWKClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.repositories import UserRepository

# In-memory JWKS cache: {"keys": [...], "fetched_at": timestamp}
_jwks_cache: dict[str, Any] = {}
_JWKS_CACHE_TTL = 3600  # 1 hour

jwks_client = PyJWKClient(
    f"{settings.HANKO_API_URL}/.well-known/jwks.json",
    cache_keys=True,
    lifespan=3600,
)

bearer_scheme = HTTPBearer()


def _get_signing_key(jwks: dict[str, Any], token: str) -> jwt.algorithms.RSAAlgorithm:
    """Extract the correct signing key from JWKS based on the token's kid header."""
    unverified_header = jwt.get_unverified_header(token)
    kid = unverified_header.get("kid")

    for key_data in jwks.get("keys", []):
        if key_data.get("kid") == kid:
            return jwt.algorithms.RSAAlgorithm.from_jwk(key_data)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unable to find matching signing key",
    )


async def get_hanko_jwks() -> dict[str, Any]:
    """Fetch Hanko JWKS from the well-known endpoint, with 1-hour cache."""
    global _jwks_cache

    now = time.time()
    if _jwks_cache and (now - _jwks_cache.get("fetched_at", 0)) < _JWKS_CACHE_TTL:
        return _jwks_cache

    jwks_url = f"{settings.HANKO_API_URL.rstrip('/')}/.well-known/jwks.json"
    async with httpx.AsyncClient() as client:
        response = await client.get(jwks_url, timeout=10.0)
        response.raise_for_status()
        jwks_data = response.json()

    _jwks_cache = {**jwks_data, "fetched_at": now}
    return _jwks_cache


async def verify_hanko_token(token: str) -> dict[str, Any]:
    """Decode and validate a Hanko JWT, returning the decoded payload.

    The payload contains at minimum:
    - sub: Hanko user ID
    - email: user's email (if available in token claims)
    - exp: expiration timestamp
    """
    jwks = await get_hanko_jwks()
    public_key = _get_signing_key(jwks, token)

    audience = settings.HANKO_AUDIENCE or None
    decode_options: dict[str, Any] = {"require": ["exp", "sub"]}
    if not audience:
        decode_options["verify_aud"] = False

    try:
        return jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=audience,
            options=decode_options,
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
        )


def _extract_token(request: Request) -> str | None:
    """Extract Bearer token from Authorization header or hanko cookie."""
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:]

    hanko_cookie = request.cookies.get("hanko")
    if hanko_cookie:
        return hanko_cookie

    return None


def _authenticate_api_key(request: Request, db: Session, token: str) -> User:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="API KEYS NOT IMPLEMENTED",
    )


def _extract_email_from_hanko_payload(payload: dict[str, Any]) -> str:
    """Hanko stores email as either a nested object or a string — normalise it."""
    email = payload.get("email", {})
    if isinstance(email, dict):
        return email.get("address", "")
    return str(email) if email else ""


async def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """FastAPI dependency: extract and verify the Hanko token, return the User.

    Looks up the user by hanko_id. If not found, auto-creates a new User record.
    Raises HTTP 401 if no valid token is present.
    """
    token = _extract_token(request)

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # API key authentication
    if token.startswith("sk_"):
        return _authenticate_api_key(request, db, token)

    # Hanko JWT authentication
    payload = await verify_hanko_token(token)

    hanko_id = payload["sub"]
    email_address = _extract_email_from_hanko_payload(payload)

    try:
        user, is_new = UserRepository(db).get_or_provision_by_hanko_id(
            hanko_id=hanko_id,
            email=email_address,
            first_name=payload.get("given_name") or "",
            last_name=payload.get("family_name") or "",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        )

    return user
