from typing import Any

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from fastapi.security import HTTPBearer
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientError
from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.repositories import UserRepository

# Single JWKS caching mechanism: PyJWKClient caches the fetched key set
# (`lifespan` seconds) and, on a `kid` it doesn't recognize, refetches the
# key set exactly once before giving up (see `PyJWKClient.get_signing_key`).
# That bounded-refresh behavior is what survives a Hanko key rotation without
# opening an unbounded outbound-fetch path for random `kid` values.
jwks_client = PyJWKClient(
    f"{settings.HANKO_API_URL}/.well-known/jwks.json",
    cache_keys=True,
    lifespan=3600,
)

bearer_scheme = HTTPBearer()


async def verify_hanko_token(token: str) -> dict[str, Any]:
    """Decode and validate a Hanko JWT, returning the decoded payload.

    The payload contains at minimum:
    - sub: Hanko user ID
    - email: user's email (if available in token claims)
    - exp: expiration timestamp
    """
    try:
        # get_signing_key_from_jwt performs blocking network I/O (urllib) on
        # a cache miss, so it runs off the event loop. It internally retries
        # at most once on an unknown kid (refresh=True) before raising.
        signing_key = await run_in_threadpool(
            jwks_client.get_signing_key_from_jwt, token
        )
    except PyJWKClientError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Unable to find matching signing key: {e}",
        )
    public_key = signing_key.key

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

    repo = UserRepository(db)
    try:
        user, is_new = repo.get_or_provision_by_hanko_id(
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

    # Stateless JWTs mean there is no login endpoint to hook, so "last
    # login" is approximated here; the touch is throttled inside the
    # repository so it is not a write per request. When the stamp actually
    # moves we treat that as a fresh sign-in and record it in the audit trail
    # with the client's IP / country / user agent, which is what makes the
    # "who signed in, from where" view possible at all.
    if repo.touch_last_login(user):
        record_audit(
            db,
            user=user,
            action="login",
            entity_type="user",
            entity_id=user.id,  # type: ignore[invalid-argument-type]
            request=request,
        )

    return user
