"""Capture a screenshot of an open Dialog at mobile width to verify Phase 01 fix."""
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT_DIR = Path(__file__).parent
DESKTOP_PATH = OUT_DIR / "phase-01-desktop-dialog.png"
MOBILE_PATH = OUT_DIR / "phase-01-mobile-dialog.png"


def open_fund_dialog(page) -> bool:
    """Click 'New fund' to open the FundCreateDialog. Returns True if a dialog appeared."""
    page.goto("http://localhost:3002/funds", wait_until="domcontentloaded")
    # Wait until the page chrome renders (network idle)
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        pass

    # Try several selectors for the trigger button
    btn = None
    for sel in ('button:has-text("New fund")', 'button:has-text("Create fund")'):
        loc = page.locator(sel).first
        if loc.count() > 0:
            btn = loc
            break

    if btn is None:
        return False

    btn.click()
    try:
        page.wait_for_selector('[data-slot="dialog-content"]', timeout=5000)
    except Exception:
        return False
    page.wait_for_timeout(400)
    return True


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # ---- Mobile capture (iPhone 14 width) ----
        mobile_ctx = browser.new_context(
            viewport={"width": 390, "height": 844},
            device_scale_factor=2,
            is_mobile=True,
            has_touch=True,
        )
        mobile = mobile_ctx.new_page()
        mobile_console: list[str] = []
        mobile.on("console", lambda msg: mobile_console.append(f"[{msg.type}] {msg.text}"))

        if open_fund_dialog(mobile):
            mobile.screenshot(path=str(MOBILE_PATH), full_page=False)
            print(f"mobile dialog captured -> {MOBILE_PATH}")
        else:
            mobile.screenshot(path=str(MOBILE_PATH), full_page=False)
            print(f"mobile fallback (page only) -> {MOBILE_PATH}")
            for line in mobile_console[-10:]:
                print("  console:", line)

        mobile_ctx.close()

        # ---- Desktop capture for comparison ----
        desktop_ctx = browser.new_context(
            viewport={"width": 1280, "height": 800},
        )
        desktop = desktop_ctx.new_page()
        desktop_console: list[str] = []
        desktop.on("console", lambda msg: desktop_console.append(f"[{msg.type}] {msg.text}"))

        if open_fund_dialog(desktop):
            desktop.screenshot(path=str(DESKTOP_PATH), full_page=False)
            print(f"desktop dialog captured -> {DESKTOP_PATH}")
        else:
            desktop.screenshot(path=str(DESKTOP_PATH), full_page=False)
            print(f"desktop fallback (page only) -> {DESKTOP_PATH}")
            for line in desktop_console[-10:]:
                print("  console:", line)

        desktop_ctx.close()
        browser.close()


if __name__ == "__main__":
    main()
