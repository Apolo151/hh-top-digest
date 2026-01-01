from playwright.sync_api import sync_playwright

URL = "https://playwright.dev/"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    page.goto(URL)
    print(page.title())
    # page.screenshot(path="example.png")
    browser.close()