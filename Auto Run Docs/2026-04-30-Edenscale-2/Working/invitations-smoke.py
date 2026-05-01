"""Unauthenticated smoke probe for Phase 07's invitation routes.

We can't drive the full demo flow (Hanko magic links require real email delivery,
plus we'd need a seeded superadmin and a fresh DB). What we *can* verify here:

  1. /invitations/accept?token=abc bounces an unauthenticated visitor to
     /login with next=<encoded original URL incl. the token>.
  2. /invitations/accept (no token) also bounces.
  3. After bouncing, the LoginPage renders without uncaught JS errors.
  4. The frontend bundle compiles and serves without compile-time errors.

Anything beyond that needs the manual demo flow described in
Phase-07-Invitations-Frontend.md task #7.
"""

from __future__ import annotations

import sys
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import sync_playwright

BASE = "http://localhost:3000"
TOKEN = "smoke-token-abc-123"

cases = [
    {
        "label": "with-token",
        "url": f"{BASE}/invitations/accept?token={TOKEN}",
        "expected_next": f"/invitations/accept?token={TOKEN}",
    },
    {
        "label": "no-token",
        "url": f"{BASE}/invitations/accept",
        "expected_next": "/invitations/accept",
    },
]


def is_expected(err: str) -> bool:
    lowered = err.lower()
    if "[pageerror]" in lowered:
        return False
    return any(
        s in lowered
        for s in [
            "status of 401",
            "status of 404",
            "unauthorized",
        ]
    )


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    failures: list[str] = []

    for case in cases:
        page = browser.new_page()
        errors: list[str] = []
        page.on(
            "console",
            lambda msg, errors=errors: errors.append(f"[console.error] {msg.text}")
            if msg.type == "error"
            else None,
        )
        page.on(
            "pageerror",
            lambda exc, errors=errors: errors.append(f"[pageerror] {exc}"),
        )

        page.goto(case["url"])
        try:
            page.wait_for_url("**/login*", timeout=8000)
        except Exception as exc:
            failures.append(f"{case['label']}: never landed on /login ({exc})")
            page.close()
            continue

        try:
            page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass

        landed_url = page.url
        parsed = urlparse(landed_url)
        qs = parse_qs(parsed.query)
        next_param = (qs.get("next") or [""])[0]

        if parsed.path != "/login":
            failures.append(f"{case['label']}: expected path /login, got {parsed.path}")
        if next_param != case["expected_next"]:
            failures.append(
                f"{case['label']}: expected next={case['expected_next']!r}, got {next_param!r}"
            )

        body = page.locator("body").inner_text()[:200].replace("\n", " | ")
        unexpected = [e for e in errors if not is_expected(e)]
        if unexpected:
            failures.append(f"{case['label']}: unexpected errors {unexpected}")

        print(f"== {case['label']} ==")
        print(f"  landed = {landed_url}")
        print(f"  next   = {next_param}")
        print(f"  body   = {body}")
        page.close()

    browser.close()

if failures:
    print()
    print("FAIL")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)

print()
print("OK: /invitations/accept correctly redirects unauthenticated visitors to /login with next=preserved.")
