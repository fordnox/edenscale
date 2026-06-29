"""Confirm the mobile drawer's bottom user-menu opens upward correctly."""

from playwright.sync_api import sync_playwright

OUT = "/Users/andy/Developer/edenscale/Auto Run Docs/Working"


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, has_touch=True)
    page = ctx.new_page()

    page.goto("http://localhost:3000/")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(500)

    # Hide toaster region so it doesn't visually overlap the drawer bottom
    page.add_style_tag(content="[data-sonner-toaster]{display:none !important}")

    # Open drawer
    page.locator('button[aria-label="Open navigation"]').first.click()
    page.wait_for_timeout(600)
    page.screenshot(path=f"{OUT}/mobile_drawer_clean.png", full_page=False)

    # Locate the user-menu trigger inside the drawer specifically
    drawer = page.locator('[data-slot="drawer-content"]').first
    user_trigger = drawer.locator('button[aria-label="Open user menu"]').first
    visible = user_trigger.is_visible()
    print(f"drawer user-menu trigger visible: {visible}")
    if visible:
        box = user_trigger.bounding_box()
        print(f"trigger box: {box}")
        user_trigger.click()
        page.wait_for_timeout(400)
        menu = page.locator('[data-slot="dropdown-menu-content"]').first
        print(f"menu visible: {menu.is_visible()}")
        if menu.is_visible():
            items = menu.locator('[data-slot="dropdown-menu-item"]').all_text_contents()
            print(f"menu items: {items}")
            cb = menu.bounding_box()
            tb = box
            opens_up = cb["y"] + cb["height"] <= tb["y"] + 8
            print(f"opens upward: {opens_up}")
        page.screenshot(path=f"{OUT}/mobile_drawer_usermenu.png", full_page=False)

    browser.close()
