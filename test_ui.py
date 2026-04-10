from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    
    # Step 1: Navigate to the page
    print("Step 1: Navigating to http://localhost:5002/")
    page.goto("http://localhost:5002/")
    page.wait_for_load_state('networkidle')
    
    # Take first screenshot
    page.screenshot(path='/tmp/step1_initial_page.png', full_page=True)
    print("✓ Screenshot 1 saved to /tmp/step1_initial_page.png")
    
    # Get initial page structure
    print("\n=== INITIAL PAGE STATE ===")
    print(f"Title: {page.title()}")
    
    # Find all buttons
    buttons = page.locator('button').all()
    print(f"Found {len(buttons)} buttons on the page")
    for i, btn in enumerate(buttons):
        text = btn.text_content()
        if text:
            print(f"  Button {i}: {text}")
    
    # Step 2: Click on a sample question button (looking for "Karma" or similar)
    print("\nStep 2: Clicking on a sample question button...")
    
    # Try to find and click the Karma button or any sample question button
    karma_button = page.get_by_text("Karma", exact=False)
    if karma_button.count() > 0:
        print("Found 'Karma' button, clicking it...")
        karma_button.first.click()
    else:
        # Try to find any button that looks like a sample question
        print("'Karma' button not found, looking for other sample question buttons...")
        all_buttons = page.locator('button').all()
        for btn in all_buttons:
            text = btn.text_content()
            if text and len(text) > 3:  # Sample question buttons likely have meaningful text
                print(f"Clicking button: {text}")
                btn.click()
                break
    
    # Wait for response (15-20 seconds as requested)
    print("Waiting for LLM response (20 seconds)...")
    time.sleep(20)
    
    # Take second screenshot showing the answer
    page.screenshot(path='/tmp/step2_with_answer.png', full_page=True)
    print("✓ Screenshot 2 saved to /tmp/step2_with_answer.png")
    
    # Get page state with answer
    print("\n=== PAGE STATE AFTER QUERY ===")
    
    # Try to find answer/response elements
    page_content = page.content()
    
    # Look for answer text or source verses
    answers = page.locator('[class*="answer"], [class*="response"], [class*="result"]').all()
    print(f"Found {len(answers)} potential answer elements")
    
    sources = page.locator('[class*="source"], [class*="verse"], [class*="scripture"]').all()
    print(f"Found {len(sources)} potential source/verse elements")
    
    browser.close()
    
print("\n✓ Automation complete!")
