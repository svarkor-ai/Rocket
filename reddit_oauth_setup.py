import os
import json
from playwright.sync_api import sync_playwright

def setup_reddit_oauth():
    with sync_playwright() as p:
        browser = p.firefox.launch(headless=True)
        page = browser.new_page()
        
        # Go to Reddit login
        print("Navigating to Reddit login...")
        page.goto("https://www.reddit.com/login")
        page.wait_for_timeout(3000)  # Wait for JS challenge
        
        # Try to detect and wait for challenge to complete
        while 'js_challenge' in page.url:
            print("Waiting for JS challenge...")
            page.wait_for_timeout(2000)
            
        # Fill login form
        print("Logging in...")
        page.fill('input[name="username"]', 'lektove@gmail.com')
        page.fill('input[name="password"]', 'Alst3836')
        page.click('button[type="submit"]')
        page.wait_for_timeout(5000)  # Wait for login
        
        # Check if login succeeded
        if 'login' in page.url and 'reddit' in page.url:
            print("Login failed!")
            page.screenshot(path="/tmp/reddit_login_fail.png")
            browser.close()
            return None
            
        print("Login successful! URL:", page.url)
        
        # Go to app preferences
        print("Going to app preferences...")
        page.goto("https://www.reddit.com/prefs/apps")
        page.wait_for_timeout(3000)
        
        # Look for create app button
        print("Looking for create button...")
        create_btn = page.query_selector('button:has-text("create")')
        if not create_btn:
            create_btn = page.query_selector('[data-testid="create-app-button"]')
        if not create_btn:
            # Screenshot for debugging
            page.screenshot(path="/tmp/reddit_prefs_debug.png")
            print("Debug screenshot saved")
            browser.close()
            return None
            
        create_btn.click()
        page.wait_for_timeout(2000)
        
        # Fill app details
        print("Filling app details...")
        page.fill('input[name="name"]', 'RocketScanner')
        page.fill('input[name="description"]', 'Stock scanner')
        page.fill('input[name="url"]', 'http://localhost:8080')
        page.fill('input[name="redirect_uri"]', 'http://localhost:8080')
        
        # Select type
        type_select = page.query_selector('select[name="type"]')
        if type_select:
            type_select.select_option(value='script')
            
        # Submit
        submit_btn = page.query_selector('button[type="submit"]')
        if not submit_btn:
            submit_btn = page.query_selector('button:has-text("create"), button:has-text("submit")')
            
        if submit_btn:
            submit_btn.click()
            page.wait_for_timeout(3000)
        else:
            print("No submit button found")
            page.screenshot(path="/tmp/reddit_submit_fail.png")
            browser.close()
            return None
            
        # Extract credentials
        print("Extracting credentials...")
        client_id = page.query_selector('input[name="client_id"], #client_id, [id*="client_id"]')
        client_secret = page.query_selector('input[name="client_secret"], #client_secret, [id*="client_secret"]')
        
        if client_id and client_secret:
            client_id_val = client_id.input_value()
            client_secret_val = client_secret.input_value()
            print("Success!")
            print("Client ID:", client_id_val[:20] + "...")
            print("Client Secret:", client_secret_val[:20] + "...")
            browser.close()
            return {"client_id": client_id_val, "client_secret": client_secret_val}
        else:
            print("Could not find credentials")
            page.screenshot(path="/tmp/reddit_creds.png")
            browser.close()
            return None

if __name__ == "__main__":
    creds = setup_reddit_oauth()
    if creds:
        env_file = '/home/svarkor/svarkor/builds/rocket-stock-scanner/.env'
        with open(env_file, 'r') as f:
            content = f.read()
            
        # Update or append credentials
        if 'REDDIT_CLIENT_ID=' in content:
            content = content.replace('REDDIT_CLIENT_ID=', 'REDDIT_CLIENT_ID=' + creds['client_id'] + '\n')
        else:
            content += 'REDDIT_CLIENT_ID=' + creds['client_id'] + '\n'
            
        if 'REDDIT_CLIENT_SECRET=' in content:
            content = content.replace('REDDIT_CLIENT_SECRET=', 'REDDIT_CLIENT_SECRET=' + creds['client_secret'] + '\n')
        else:
            content += 'REDDIT_CLIENT_SECRET=' + creds['client_secret'] + '\n'
            
        with open(env_file, 'w') as f:
            f.write(content)
            
        print("Updated .env file")
    else:
        print("Failed to create OAuth app")
