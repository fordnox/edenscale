"""Tests for JWKS key rotation handling in ``app.core.auth``.

Hanko rotates its signing key periodically. A token signed with a `kid` that
isn't in the cached key set must trigger exactly one forced refetch before
either succeeding (new key now present) or failing closed with 401 (kid still
unknown). The load-bearing assertion in every test here is the **number of
outbound JWKS fetches** — not just the pass/fail outcome — because an
unbounded refetch-on-miss path would let anyone force repeated outbound calls
by sending tokens with random `kid` values.

No real network calls are made: the one line in ``PyJWKClient.fetch_data``
that actually hits the network, ``urllib.request.urlopen``, is monkeypatched
per test with an in-memory fake. That is deliberate rather than mocking
``fetch_data`` itself — ``fetch_data`` is also what populates
``PyJWKClient``'s internal ``jwk_set_cache``, so stubbing it directly would
silently defeat the very caching this test is verifying.

Each test gets its own freshly constructed ``PyJWKClient`` (swapped in for
``auth.jwks_client``) so cache state never leaks between tests or from the
module-level singleton.
"""

import asyncio
import io
import time
import uuid

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt import PyJWKClient
from jwt.algorithms import RSAAlgorithm

from app.core import auth


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def _make_rsa_keypair(kid: str):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    jwk = RSAAlgorithm.to_jwk(public_key, as_dict=True)
    jwk["kid"] = kid
    jwk["use"] = "sig"
    jwk["alg"] = "RS256"
    return private_key, jwk


def _make_token(private_key, kid: str) -> str:
    now = int(time.time())
    return jwt.encode(
        {"sub": str(uuid.uuid4()), "exp": now + 3600, "iat": now},
        private_key,
        algorithm="RS256",
        headers={"kid": kid},
    )


class _FakeHttpResponse(io.BytesIO):
    """Minimal stand-in for the object ``urllib.request.urlopen`` yields —
    just enough for ``json.load(response)`` and the ``with`` block."""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _FakeUrlopen:
    """Drop-in for ``urllib.request.urlopen`` that serves canned JWKS bodies
    and counts every outbound "fetch" — the thing this test actually cares
    about pinning."""

    def __init__(self, bodies: list[bytes]):
        self._bodies = list(bodies)
        self.call_count = 0

    def __call__(self, request, timeout=None, context=None):
        self.call_count += 1
        if not self._bodies:
            raise AssertionError("unexpected extra JWKS fetch")
        # Clamp to the last body once exhausted, so a test with a single
        # canned response can still assert a *count* of repeat calls without
        # needing one queued body per call.
        index = min(self.call_count - 1, len(self._bodies) - 1)
        return _FakeHttpResponse(self._bodies[index])


@pytest.fixture
def fresh_jwks_client(monkeypatch):
    """A JWKClient identical in construction to auth.jwks_client, but private
    to this test — no shared cache state, no lru_cache pollution.
    """
    client = PyJWKClient(
        "https://hanko.example.invalid/.well-known/jwks.json",
        cache_keys=True,
        lifespan=3600,
    )
    monkeypatch.setattr(auth, "jwks_client", client)
    # Audience checking is out of scope for this test; unset it so the test
    # only exercises key retrieval, not validation semantics.
    monkeypatch.setattr(auth.settings, "HANKO_AUDIENCE", "")
    return client


class TestJwksRotation:
    def test_unknown_kid_triggers_exactly_one_refetch_then_succeeds(
        self, fresh_jwks_client, monkeypatch
    ):
        import json

        key1_priv, key1_jwk = _make_rsa_keypair("kid-1")
        key2_priv, key2_jwk = _make_rsa_keypair("kid-2")

        old_body = json.dumps({"keys": [key1_jwk]}).encode()
        new_body = json.dumps({"keys": [key1_jwk, key2_jwk]}).encode()
        fake_urlopen = _FakeUrlopen([old_body, new_body])
        monkeypatch.setattr("jwt.jwks_client.urllib.request.urlopen", fake_urlopen)

        # Warm the cache with a token signed by the already-known key — one
        # real fetch, nothing to refresh.
        token1 = _make_token(key1_priv, "kid-1")
        payload1 = _run(auth.verify_hanko_token(token1))
        assert payload1["sub"]
        assert fake_urlopen.call_count == 1

        # A token signed with the rotated key (kid-2) is unknown to the
        # cached set — this must trigger exactly one forced refetch, after
        # which the new key is present and the token validates.
        token2 = _make_token(key2_priv, "kid-2")
        payload2 = _run(auth.verify_hanko_token(token2))
        assert payload2["sub"]
        assert fake_urlopen.call_count == 2

    def test_unknown_kid_after_refetch_raises_401_without_extra_fetches(
        self, fresh_jwks_client, monkeypatch
    ):
        import json

        key1_priv, key1_jwk = _make_rsa_keypair("kid-1")
        rogue_priv, _rogue_jwk = _make_rsa_keypair("kid-rogue")

        # Every fetch returns the same set — the rogue kid is never present,
        # simulating a token signed by a key Hanko never published (or an
        # attacker probing with a random kid).
        body = json.dumps({"keys": [key1_jwk]}).encode()
        fake_urlopen = _FakeUrlopen([body])
        monkeypatch.setattr("jwt.jwks_client.urllib.request.urlopen", fake_urlopen)

        # Warm the cache.
        token1 = _make_token(key1_priv, "kid-1")
        _run(auth.verify_hanko_token(token1))
        assert fake_urlopen.call_count == 1

        rogue_token = _make_token(rogue_priv, "kid-rogue")

        with pytest.raises(Exception) as exc_info:
            _run(auth.verify_hanko_token(rogue_token))
        # HTTPException carries a status_code attribute.
        assert getattr(exc_info.value, "status_code", None) == 401

        # Exactly one forced refresh was attempted for the unknown kid on top
        # of the warm-up fetch — not a second, third, ... attempt.
        assert fake_urlopen.call_count == 2
