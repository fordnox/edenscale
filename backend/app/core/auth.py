from urllib.parse import urlsplit

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from app.core.config import settings

# Neon Auth signs session JWTs with EdDSA (Ed25519) and publishes its public
# keys at "{NEON_AUTH_URL}/.well-known/jwks.json". The token issuer (`iss`) is
# the origin of the auth URL (scheme + host, no path).
_auth_origin = urlsplit(settings.NEON_AUTH_URL)
NEON_AUTH_ISSUER = (
    f"{_auth_origin.scheme}://{_auth_origin.netloc}" if _auth_origin.netloc else ""
)

jwks_client = PyJWKClient(
    f"{settings.NEON_AUTH_URL}/.well-known/jwks.json",
    cache_keys=True,
    lifespan=3600,
)

bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    token = credentials.credentials
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["EdDSA"],
            issuer=NEON_AUTH_ISSUER,
            # Neon Auth tokens are not minted with an audience claim aimed at this
            # API, so audience verification is disabled (issuer + signature are
            # the trust anchors).
            options={"verify_aud": False},
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )
    return payload
