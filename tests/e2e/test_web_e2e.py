import os

import pytest


@pytest.mark.e2e
@pytest.mark.skipif(os.getenv("RUN_E2E") != "1", reason="Set RUN_E2E=1 to run browser tests")
def test_home_to_login_navigation_e2e():
    from playwright.sync_api import sync_playwright

    base_url = os.getenv("E2E_BASE_URL", "http://127.0.0.1:8000")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(base_url, wait_until="networkidle")
        page.get_by_role("link", name="Login").click()
        page.wait_for_url(f"{base_url}/login")
        page.get_by_role("heading", name="Welcome Back").is_visible()
        browser.close()
