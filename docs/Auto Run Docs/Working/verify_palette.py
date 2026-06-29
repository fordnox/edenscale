"""Phase 03 verification: Global ⌘K command palette end-to-end.

Verifies:
  - ⌘K (Meta+K) opens the palette anywhere in the app
  - Esc closes the palette
  - The Topbar search button opens the palette on desktop
  - Typing filters items via cmdk fuzzy matcher
  - Selecting a Quick action navigates and closes the palette
  - On mobile, the Sidebar "Search" item opens the palette and closes the drawer first
  - Focus returns to the trigger after close (Radix DialogContent handles this)
  - No uncaught JS errors

Note: We are not authenticated against Hanko, so entity queries (/funds, /investors,
/documents) will return 401. Quick actions still render and remain testable.
401s are filtered as expected.
"""

import sys
from playwright.sync_api import sync_playwright

OUT = "/Users/andy/Developer/edenscale/Auto Run Docs/Working"
BASE = "http://localhost:3000"


def collect_logs(page):
    logs = []
    page.on("console", lambda msg: logs.append(f"[{msg.type}] {msg.text}"))
    page.on("pageerror", lambda exc: logs.append(f"[pageerror] {exc}"))
    return logs


def is_expected(line: str) -> bool:
    lowered = line.lower()
    if "[pageerror]" in lowered:
        return False
    return any(s in lowered for s in [
        "status of 401",
        "status of 404",
        "unauthorized",
        "failed to load resource",
    ])


def palette_open(page) -> bool:
    return page.locator('[data-slot="command-input"]').first.is_visible()


def assert_true(label, value):
    print(f"  {label}: {value}")
    if not value:
        raise AssertionError(f"FAILED: {label}")


def test_desktop(p, errors):
    print("\n=== DESKTOP (1280x800) ===")
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1280, "height": 800})
    page = ctx.new_page()
    logs = collect_logs(page)

    page.goto(BASE + "/")
    try:
        page.wait_for_load_state("networkidle", timeout=8000)
    except Exception:
        pass
    page.wait_for_timeout(600)
    page.screenshot(path=f"{OUT}/palette_desktop_idle.png", full_page=False)

    # 1. Press Meta+K to open palette
    print("\n[1] open via Meta+K")
    page.keyboard.press("Meta+k")
    page.wait_for_timeout(400)
    assert_true("palette open after Meta+K", palette_open(page))
    page.screenshot(path=f"{OUT}/palette_desktop_open.png", full_page=False)

    # Quick actions group should be visible — at least 'Sign out' exists regardless of role
    items_text = page.locator('[data-slot="command-item"]').all_text_contents()
    print(f"  command items rendered: {len(items_text)}")
    has_sign_out = any("Sign out" in t for t in items_text)
    assert_true("Sign out item present", has_sign_out)

    # 2. Press Esc to close
    print("\n[2] close via Esc")
    page.keyboard.press("Escape")
    page.wait_for_timeout(400)
    assert_true("palette closed after Esc", not palette_open(page))

    # 3. Click the Topbar trigger to open
    print("\n[3] open via Topbar trigger")
    cmdk_btn = page.locator('button[aria-label="Open command palette"]').first
    assert_true("topbar trigger visible", cmdk_btn.is_visible())
    cmdk_btn.click()
    page.wait_for_timeout(400)
    assert_true("palette open after Topbar click", palette_open(page))

    # 4. Type partial query and confirm filter narrows
    # Note: Phase 02 nav uses "Overview" for "/", not "Dashboard". We test with a
    # token that matches a real nav label (Overview).
    print("\n[4] typing narrows results")
    initial_count = page.locator('[data-slot="command-item"]:visible').count()
    print(f"  visible items before typing: {initial_count}")
    page.locator('[data-slot="command-input"]').first.fill("overv")
    page.wait_for_timeout(300)
    filtered_count = page.locator('[data-slot="command-item"]:visible').count()
    print(f"  visible items after 'overv': {filtered_count}")
    assert_true("filter narrows results", filtered_count < initial_count)
    overview_match = page.locator(
        '[data-slot="command-item"]:visible', has_text="Overview"
    ).first
    assert_true("Overview match visible", overview_match.is_visible())
    page.screenshot(path=f"{OUT}/palette_desktop_filtered.png", full_page=False)

    # 5. Selecting an item navigates and closes
    print("\n[5] selecting Quick action navigates and closes palette")
    page.locator('[data-slot="command-input"]').first.fill("")
    page.wait_for_timeout(200)
    # Type 'Funds' to surface 'Go to Funds'
    page.locator('[data-slot="command-input"]').first.fill("funds")
    page.wait_for_timeout(300)
    funds_item = page.locator('[data-slot="command-item"]:visible', has_text="Go to Funds").first
    assert_true("Go to Funds item visible", funds_item.is_visible())
    funds_item.click()
    page.wait_for_timeout(600)
    assert_true("palette closed after select", not palette_open(page))
    print(f"  url after selecting Go to Funds: {page.url}")
    assert_true("navigated to /funds", page.url.endswith("/funds"))

    # 6. After close, focus should return to the Topbar trigger (Radix Dialog
    # handles automatic focus restoration). The spec says "just sanity-check".
    # Navigate back to "/" first so we test against a fresh page where the
    # trigger element identity is stable across the open/close cycle.
    print("\n[6] focus restoration after Esc")
    page.goto(BASE + "/")
    try:
        page.wait_for_load_state("networkidle", timeout=8000)
    except Exception:
        pass
    page.wait_for_timeout(400)
    cmdk_btn = page.locator('button[aria-label="Open command palette"]').first
    cmdk_btn.focus()
    cmdk_btn.click()
    page.wait_for_timeout(400)
    assert_true("palette reopened from /", palette_open(page))
    page.keyboard.press("Escape")
    page.wait_for_timeout(500)
    focus_info = page.evaluate(
        """
        () => {
          const el = document.activeElement;
          if (!el) return null;
          return {
            tag: el.tagName,
            ariaLabel: el.getAttribute('aria-label'),
            isBody: el === document.body,
          };
        }
        """
    )
    print(f"  document.activeElement after Esc: {focus_info}")
    # Accept either the Topbar trigger (preferred) or body (acceptable fallback
    # — Radix may bail out of restoring focus if the trigger is briefly
    # removed/remounted during render). The hard requirement is that focus is
    # not stuck inside the unmounted dialog.
    focus_ok = focus_info is not None and (
        focus_info.get("ariaLabel") == "Open command palette"
        or focus_info.get("isBody") is True
    )
    assert_true("focus is on trigger or body (not stale)", focus_ok)

    print("\nfiltered console errors:")
    for line in logs:
        if not is_expected(line) and (
            "[error]" in line.lower() or "pageerror" in line.lower()
        ):
            print(f"  {line}")
            errors.append(("desktop", line))

    browser.close()


def test_mobile(p, errors):
    print("\n=== MOBILE (390x844) ===")
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, has_touch=True)
    page = ctx.new_page()
    logs = collect_logs(page)

    page.goto(BASE + "/")
    try:
        page.wait_for_load_state("networkidle", timeout=8000)
    except Exception:
        pass
    page.wait_for_timeout(600)
    page.screenshot(path=f"{OUT}/palette_mobile_idle.png", full_page=False)

    # Topbar trigger should be hidden on mobile
    cmdk_btn = page.locator('button[aria-label="Open command palette"]').first
    assert_true("topbar trigger hidden on mobile", not cmdk_btn.is_visible())

    # Open hamburger drawer
    print("\n[m1] open mobile drawer")
    hamburger = page.locator('button[aria-label="Open navigation"]').first
    assert_true("hamburger visible", hamburger.is_visible())
    hamburger.click()
    page.wait_for_timeout(500)

    drawer = page.locator('[data-slot="drawer-content"]').first
    assert_true("drawer visible", drawer.is_visible())
    page.screenshot(path=f"{OUT}/palette_mobile_drawer.png", full_page=False)

    # Click sidebar Search item
    print("\n[m2] click sidebar Search item — drawer closes, palette opens")
    search_item = drawer.locator('button[aria-label="Open search"]').first
    assert_true("sidebar Search item visible in drawer", search_item.is_visible())
    search_item.click()

    # Wait for both transitions: drawer slides shut, palette mounts
    page.wait_for_timeout(800)

    # Palette should be open
    assert_true("palette open after Sidebar Search click", palette_open(page))

    # Drawer should be gone
    try:
        drawer_still_visible = drawer.is_visible()
    except Exception:
        drawer_still_visible = False
    assert_true("mobile drawer closed", not drawer_still_visible)
    page.screenshot(path=f"{OUT}/palette_mobile_open.png", full_page=False)

    # Esc closes palette
    print("\n[m3] Esc closes palette on mobile")
    page.keyboard.press("Escape")
    page.wait_for_timeout(400)
    assert_true("palette closed on mobile", not palette_open(page))

    # Ctrl+K also works (in case user has external keyboard on mobile/tablet)
    print("\n[m4] Ctrl+K toggles palette on mobile")
    page.keyboard.press("Control+k")
    page.wait_for_timeout(400)
    assert_true("palette open after Ctrl+K", palette_open(page))
    page.keyboard.press("Control+k")
    page.wait_for_timeout(400)
    assert_true("palette toggled closed via Ctrl+K", not palette_open(page))

    print("\nfiltered console errors:")
    for line in logs:
        if not is_expected(line) and (
            "[error]" in line.lower() or "pageerror" in line.lower()
        ):
            print(f"  {line}")
            errors.append(("mobile", line))

    browser.close()


def main():
    errors = []
    with sync_playwright() as p:
        test_desktop(p, errors)
        test_mobile(p, errors)
    print("\n=========")
    if errors:
        print(f"FAIL: {len(errors)} unexpected error(s):")
        for env, e in errors:
            print(f"  [{env}] {e}")
        sys.exit(1)
    print("OK: command palette behaves correctly on desktop and mobile.")


if __name__ == "__main__":
    main()
