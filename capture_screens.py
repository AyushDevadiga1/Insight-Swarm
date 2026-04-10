import time
import sys
from playwright.sync_api import sync_playwright

def run(playwright):
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1600, 'height': 900})
    
    print("Navigating to http://localhost:5173...")
    page.goto("http://localhost:5173")
    page.wait_for_timeout(5000)
    page.screenshot(path="outputs/test_screenshot.png")
    
    # Try to dump the HTML to see what's there
    with open("page_source.html", "w", encoding="utf-8") as f:
        f.write(page.content())
    
    print("Saved test_screenshot.png and page_source.html")
    browser.close()

if __name__ == "__main__":
    with sync_playwright() as playwright:
        run(playwright)
