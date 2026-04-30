"""Phase 02 verification: chrome end-to-end on desktop and mobile."""

from playwright.sync_api import sync_playwright

OUT = "/Users/andy/Developer/edenscale/Auto Run Docs/Working"


def collect_logs(page):
    logs = []
    page.on("console", lambda msg: logs.append(f"[{msg.type}] {msg.text}"))
    page.on("pageerror", lambda exc: logs.append(f"[pageerror] {exc}"))
    return logs


def test_desktop(p):
    print("\n=== DESKTOP (1280x800) ===")
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1280, "height": 800})
    page = ctx.new_page()
    logs = collect_logs(page)

    page.goto("http://localhost:3000/")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(800)

    page.screenshot(path=f"{OUT}/desktop_default.png", full_page=False)

    # Sidebar should be visible (desktop aside)
    aside = page.locator("aside").first
    print(f"sidebar visible: {aside.is_visible()}")

    # Topbar: hamburger should be hidden, ⌘K button visible, no bell, no user dropdown
    hamburger = page.locator('button[aria-label="Open navigation"]').first
    print(f"hamburger visible (should be False on desktop): {hamburger.is_visible()}")

    cmdk_btn = page.locator('button[aria-label="Open command palette"]').first
    print(f"⌘K button visible: {cmdk_btn.is_visible()}")

    # Bell/notifications icon in topbar should NOT exist
    bell_links = page.locator('header a[href="/notifications"]').count()
    print(f"bell link in topbar (should be 0): {bell_links}")

    # User-menu in topbar should NOT exist as a separate dropdown
    # (sidebar dropdown is fine; topbar should have no DropdownMenu)
    header = page.locator("header").first
    header_dropdowns = header.locator('[data-slot="dropdown-menu-trigger"]').count()
    print(f"dropdown triggers in topbar (should be 0): {header_dropdowns}")

    # Sidebar bottom user trigger
    user_trigger = page.locator('button[aria-label="Open user menu"]').first
    print(f"sidebar user-menu trigger visible: {user_trigger.is_visible()}")

    # Click it and screenshot to confirm it opens upward
    user_trigger.click()
    page.wait_for_timeout(300)
    page.screenshot(path=f"{OUT}/desktop_usermenu.png", full_page=False)

    # Look for menu items
    menu_content = page.locator('[data-slot="dropdown-menu-content"]').first
    if menu_content.is_visible():
        items = menu_content.locator('[data-slot="dropdown-menu-item"]').all_text_contents()
        print(f"user menu items: {items}")
        # Check vertical position relative to trigger — content should be above
        trigger_box = user_trigger.bounding_box()
        content_box = menu_content.bounding_box()
        if trigger_box and content_box:
            opens_upward = content_box["y"] + content_box["height"] <= trigger_box["y"] + 8
            print(f"opens upward: {opens_upward} (trigger.y={trigger_box['y']}, content.y={content_box['y']}, content.h={content_box['height']})")

    # Close
    page.keyboard.press("Escape")
    page.wait_for_timeout(200)

    print("\nconsole/page errors:")
    for line in logs[-30:]:
        if "[error]" in line.lower() or "pageerror" in line.lower():
            print(f"  {line}")

    browser.close()


def test_mobile(p):
    print("\n=== MOBILE (390x844, iPhone-ish) ===")
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, has_touch=True)
    page = ctx.new_page()
    logs = collect_logs(page)

    page.goto("http://localhost:3000/")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(800)

    page.screenshot(path=f"{OUT}/mobile_default.png", full_page=False)

    # Desktop aside should be hidden on mobile
    aside = page.locator("aside").first
    print(f"desktop aside visible (should be False): {aside.is_visible()}")

    # Hamburger should be visible
    hamburger = page.locator('button[aria-label="Open navigation"]').first
    print(f"hamburger visible: {hamburger.is_visible()}")

    # ⌘K button should be hidden on mobile (md:flex)
    cmdk_btn = page.locator('button[aria-label="Open command palette"]').first
    print(f"⌘K button visible on mobile (should be False): {cmdk_btn.is_visible()}")

    # Open sidebar via hamburger
    hamburger.click()
    page.wait_for_timeout(500)
    page.screenshot(path=f"{OUT}/mobile_drawer_open.png", full_page=False)

    # Drawer content should be visible
    drawer_content = page.locator('[data-slot="drawer-content"]').first
    print(f"drawer content visible: {drawer_content.is_visible()}")

    # NavLinks inside drawer
    nav_count = drawer_content.locator("nav a").count()
    print(f"nav items in drawer: {nav_count}")

    # Tap a nav link and confirm route changes + drawer closes
    if nav_count > 1:
        # Click second nav link (index 1) to trigger navigation
        target = drawer_content.locator("nav a").nth(1)
        href = target.get_attribute("href")
        print(f"clicking nav target href={href}")
        target.click()
        page.wait_for_timeout(700)
        print(f"url after click: {page.url}")
        # Drawer should auto-close
        try:
            still_open = drawer_content.is_visible()
        except Exception:
            still_open = False
        print(f"drawer still open after route change (should be False): {still_open}")
        page.screenshot(path=f"{OUT}/mobile_after_navclick.png", full_page=False)

    # Re-open and try sidebar bottom user-menu
    hamburger2 = page.locator('button[aria-label="Open navigation"]').first
    hamburger2.click()
    page.wait_for_timeout(500)
    user_trigger = page.locator('button[aria-label="Open user menu"]').first
    print(f"sidebar user trigger visible in drawer: {user_trigger.is_visible()}")
    if user_trigger.is_visible():
        user_trigger.click()
        page.wait_for_timeout(300)
        page.screenshot(path=f"{OUT}/mobile_usermenu.png", full_page=False)
        menu_content = page.locator('[data-slot="dropdown-menu-content"]').first
        print(f"user menu visible: {menu_content.is_visible()}")
        if menu_content.is_visible():
            items = menu_content.locator('[data-slot="dropdown-menu-item"]').all_text_contents()
            print(f"user menu items: {items}")
            trigger_box = user_trigger.bounding_box()
            content_box = menu_content.bounding_box()
            if trigger_box and content_box:
                opens_upward = content_box["y"] + content_box["height"] <= trigger_box["y"] + 8
                print(f"opens upward: {opens_upward}")

    page.keyboard.press("Escape")
    page.wait_for_timeout(300)

    # Test swipe-to-close — Vaul accepts pointer drag on the content
    # Reopen the drawer
    page.keyboard.press("Escape")
    page.wait_for_timeout(200)
    hamb3 = page.locator('button[aria-label="Open navigation"]').first
    if hamb3.is_visible():
        hamb3.click()
        page.wait_for_timeout(500)

    drawer_content = page.locator('[data-slot="drawer-content"]').first
    if drawer_content.is_visible():
        box = drawer_content.bounding_box()
        if box:
            start_x = box["x"] + box["width"] - 20
            start_y = box["y"] + box["height"] / 2
            end_x = box["x"] - 20
            end_y = start_y
            print(f"simulating swipe from ({start_x},{start_y}) to ({end_x},{end_y})")
            page.mouse.move(start_x, start_y)
            page.mouse.down()
            # gradually move
            steps = 15
            for i in range(1, steps + 1):
                cx = start_x + (end_x - start_x) * i / steps
                page.mouse.move(cx, start_y, steps=1)
                page.wait_for_timeout(15)
            page.mouse.up()
            page.wait_for_timeout(800)
            page.screenshot(path=f"{OUT}/mobile_after_swipe.png", full_page=False)
            try:
                visible_after_swipe = drawer_content.is_visible()
            except Exception:
                visible_after_swipe = False
            print(f"drawer visible after swipe (should be False): {visible_after_swipe}")

    print("\nconsole/page errors:")
    for line in logs[-30:]:
        if "[error]" in line.lower() or "pageerror" in line.lower():
            print(f"  {line}")

    browser.close()


def main():
    with sync_playwright() as p:
        test_desktop(p)
        test_mobile(p)


if __name__ == "__main__":
    main()
