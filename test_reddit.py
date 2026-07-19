from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.firefox.launch(headless=True)
    page = browser.new_page()
    page.goto('https://www.reddit.com')
    page.wait_for_timeout(2000)
    print("Page title:", page.title())
    print("Page URL:", page.url)
    if 'login' in page.url:
        print("Redirected to login")
    browser.close()
