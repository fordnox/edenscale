"""Smoke test for the four ported pages: Documents, Letters, Tasks, Notifications.

We can't fully exercise the upload/send/mark-read flows without Hanko credentials and
a seeded dev DB, but we *can* verify:
  - the frontend bundle has no compile-time errors,
  - each /documents, /letters, /tasks, /notifications route mounts without runtime errors,
  - no unexpected page errors (uncaught JS exceptions) on any route.
401s/404s from the API are expected (we are unauthenticated) and are filtered out.
"""

import sys
from playwright.sync_api import sync_playwright

ROUTES = ["/", "/login", "/documents", "/letters", "/tasks", "/notifications"]
BASE = "http://localhost:3000"

current_route = ""
errors_by_route: dict[str, list[str]] = {r: [] for r in ROUTES}

def on_console(msg):
    if msg.type == "error":
        errors_by_route[current_route].append(f"[console.error] {msg.text}")

def on_pageerror(exc):
    errors_by_route[current_route].append(f"[pageerror] {exc}")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.on("console", on_console)
    page.on("pageerror", on_pageerror)

    for route in ROUTES:
        current_route = route
        page.goto(BASE + route)
        try:
            page.wait_for_load_state("networkidle", timeout=8000)
        except Exception as e:
            errors_by_route[route].append(f"[load-state] {e}")

        body_text = page.locator("body").inner_text()[:160].replace("\n", " | ")
        print(f"== {route} ==")
        print(f"  body = {body_text}")

    browser.close()

# Filter expected unauth API failures
def is_expected(err: str) -> bool:
    lowered = err.lower()
    if "[pageerror]" in lowered:
        return False  # never silence uncaught JS exceptions
    return any(s in lowered for s in [
        "status of 401",
        "status of 404",
        "unauthorized",
    ])

unexpected = {r: [e for e in errs if not is_expected(e)] for r, errs in errors_by_route.items()}
total_unexpected = sum(len(v) for v in unexpected.values())
print()
print(f"Routes probed: {len(ROUTES)}")
print(f"Unexpected errors: {total_unexpected}")
if total_unexpected:
    for r, errs in unexpected.items():
        if errs:
            print(f"  {r}:")
            for e in errs:
                print(f"    - {e}")
    sys.exit(1)
print("OK: no uncaught JS exceptions or unexpected runtime errors on the four ported pages.")
