"""
Playwright test script for OryggiAI Chat functionality
Tests login and chat query flow
"""

import asyncio
from playwright.async_api import async_playwright

# Configuration
BASE_URL = "http://103.197.77.163:9000"
LOGIN_EMAIL = "priyanshu.kumar@oryggitech.com"
LOGIN_PASSWORD = "Pk123456789"


async def test_chat_flow():
    """Test the complete login and chat flow"""

    async with async_playwright() as p:
        # Launch browser (headless for CI, set to False for debugging)
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        print("=" * 60)
        print("ORYGGI AI CHAT TEST")
        print("=" * 60)

        try:
            # Step 1: Navigate to login page
            print("\n[1] Navigating to login page...")
            await page.goto(f"{BASE_URL}/tenant/login.html")
            await page.wait_for_load_state("networkidle")
            print("    Login page loaded")

            # Step 2: Fill login form
            print("\n[2] Filling login credentials...")
            await page.fill('input[type="email"], input[name="email"], #email', LOGIN_EMAIL)
            await page.fill('input[type="password"], input[name="password"], #password', LOGIN_PASSWORD)
            print(f"    Email: {LOGIN_EMAIL}")
            print(f"    Password: {'*' * len(LOGIN_PASSWORD)}")

            # Step 3: Click login button
            print("\n[3] Clicking login button...")
            await page.click('button[type="submit"], .login-btn, #loginBtn')

            # Wait for navigation after login
            await page.wait_for_timeout(3000)
            print(f"    Current URL: {page.url}")

            # Step 4: Navigate to chat page
            print("\n[4] Navigating to chat page...")
            await page.goto(f"{BASE_URL}/tenant/chat.html")
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(2000)
            print("    Chat page loaded")

            # Step 5: Check database selector
            print("\n[5] Checking database selector...")
            db_select = page.locator('#databaseSelect')
            if await db_select.count() > 0:
                db_value = await db_select.input_value()
                db_text = await db_select.locator('option:checked').text_content()
                print(f"    Selected database: {db_text}")
                print(f"    Database ID: {db_value}")
            else:
                print("    ERROR: Database selector not found!")

            # Step 6: Type a question
            print("\n[6] Typing question...")
            question = "How many total Employees are there"
            chat_input = page.locator('#chatInput')
            await chat_input.fill(question)
            print(f"    Question: {question}")

            # Step 7: Send the message
            print("\n[7] Sending message...")
            send_btn = page.locator('#sendBtn')
            await send_btn.click()

            # Wait for response (up to 60 seconds)
            print("\n[8] Waiting for AI response...")
            await page.wait_for_timeout(5000)  # Initial wait

            # Check for response message
            for i in range(12):  # Wait up to 60 seconds (12 x 5 seconds)
                messages = page.locator('.message.ai .message-content')
                count = await messages.count()
                if count > 0:
                    last_message = messages.last
                    response_text = await last_message.text_content()
                    print(f"\n[9] AI Response received!")
                    print("-" * 40)
                    print(response_text[:500] if len(response_text) > 500 else response_text)
                    print("-" * 40)

                    # Check if it's an error
                    if "error" in response_text.lower() or "quota" in response_text.lower():
                        print("\n    WARNING: Response contains error message")
                    else:
                        print("\n    SUCCESS: Chat response received!")
                    break
                else:
                    print(f"    Waiting... ({(i+1)*5} seconds)")
                    await page.wait_for_timeout(5000)
            else:
                print("\n    TIMEOUT: No response received after 60 seconds")

            # Take screenshot
            screenshot_path = "D:/OryggiAI_Service/Advance_Chatbot/scripts/chat_test_result.png"
            await page.screenshot(path=screenshot_path)
            print(f"\n[10] Screenshot saved: {screenshot_path}")

        except Exception as e:
            print(f"\n    ERROR: {str(e)}")
            # Take error screenshot
            await page.screenshot(path="D:/OryggiAI_Service/Advance_Chatbot/scripts/chat_test_error.png")
            raise

        finally:
            print("\n" + "=" * 60)
            print("TEST COMPLETED")
            print("=" * 60)
            await browser.close()


if __name__ == "__main__":
    asyncio.run(test_chat_flow())
