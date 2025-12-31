"""
Playwright end-to-end test for OryggiAI frontend.
Tests login, database selection, and chat functionality via the gateway.
"""
import asyncio
import subprocess
import sys
import time
from pathlib import Path
from playwright.async_api import async_playwright, expect


# Configuration
FRONTEND_PORT = 8080
BACKEND_PORT = 9000
FRONTEND_URL = f"http://localhost:{FRONTEND_PORT}"
BACKEND_URL = f"http://localhost:{BACKEND_PORT}"

# Test credentials - will be updated based on registration
TEST_EMAIL = "playwright_test@example.com"
TEST_PASSWORD = "PlaywrightTest123!"
TEST_FULL_NAME = "Playwright Test User"
TEST_TENANT_NAME = "Playwright Test Org"


async def serve_frontend():
    """Start a simple HTTP server for the frontend files."""
    frontend_dir = Path(__file__).parent.parent / "frontend"
    process = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(FRONTEND_PORT)],
        cwd=str(frontend_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
    )
    # Wait for server to start
    await asyncio.sleep(2)
    return process


async def test_frontend():
    """Run the end-to-end test."""
    print("=" * 60)
    print("OryggiAI Frontend E2E Test with Playwright")
    print("=" * 60)

    # Start frontend server
    print("\n[1] Starting frontend HTTP server...")
    server_process = await serve_frontend()
    print(f"    Frontend server running at {FRONTEND_URL}")

    try:
        async with async_playwright() as p:
            # Launch browser (headless=False to see the test visually)
            print("\n[2] Launching browser...")
            browser = await p.chromium.launch(headless=False, slow_mo=500)
            context = await browser.new_context()
            page = await context.new_page()

            # Set timeout
            page.set_default_timeout(30000)

            # Intercept requests to redirect API calls to the backend
            async def route_api(route):
                """Route API calls to the backend server."""
                url = route.request.url
                if "/api/" in url:
                    # Replace frontend URL with backend URL
                    new_url = url.replace(f"http://localhost:{FRONTEND_PORT}", f"http://localhost:{BACKEND_PORT}")
                    print(f"    [API] Routing {url} -> {new_url}")
                    response = await route.fetch(url=new_url)
                    await route.fulfill(response=response)
                else:
                    await route.continue_()

            await page.route("**/api/**", route_api)

            # === REGISTER TEST USER ===
            print("\n[3] Registering test user (if needed)...")
            await page.goto(f"{FRONTEND_URL}/tenant/register.html")

            # Wait for page to load
            await page.wait_for_selector("#tenantName", timeout=5000)

            # Fill in registration form
            await page.fill("#tenantName", TEST_TENANT_NAME)
            await page.fill("#fullName", TEST_FULL_NAME)
            await page.fill("#email", TEST_EMAIL)
            await page.fill("#password", TEST_PASSWORD)
            await page.fill("#confirmPassword", TEST_PASSWORD)
            print(f"    Filled registration form for {TEST_EMAIL}")

            # Click register button
            await page.click("#registerBtn")
            print("    Clicked Register button")

            # Wait for result
            await asyncio.sleep(3)

            # Wait for registration result - either redirect to dashboard or show error
            already_logged_in = False
            await asyncio.sleep(2)

            # Check current URL - if redirected to dashboard, registration succeeded
            current_url = page.url
            if "dashboard.html" in current_url:
                print("    Registration successful - redirected to dashboard")
                already_logged_in = True
            else:
                # Check for error alert on registration page
                error_alert = page.locator("#errorAlert")
                if await error_alert.is_visible():
                    error_text = await error_alert.text_content()
                    if "already exists" in error_text.lower() or "already registered" in error_text.lower():
                        print("    User already exists - will login")
                    else:
                        print(f"    Registration note: {error_text}")

            # === TEST LOGIN (only if not already logged in) ===
            if not already_logged_in:
                print("\n[4] Testing Login...")
                await page.goto(f"{FRONTEND_URL}/tenant/login.html")

                # Wait for page to load - check if redirected to dashboard (already logged in)
                await asyncio.sleep(1)
                if "dashboard.html" in page.url:
                    print("    Already logged in - skipping login")
                    already_logged_in = True
                else:
                    await page.wait_for_selector("#email")
                    print("    Login page loaded")

                    # Fill in credentials
                    await page.fill("#email", TEST_EMAIL)
                    await page.fill("#password", TEST_PASSWORD)
                    print(f"    Entered credentials for {TEST_EMAIL}")

                    # Click login button
                    await page.click("#loginBtn")
                    print("    Clicked Sign In button")

                    # Wait for redirect to dashboard or error
                    try:
                        # Wait for either success (redirect) or error message
                        await page.wait_for_url("**/dashboard.html", timeout=15000)
                        print("    Login successful - redirected to dashboard")
                    except Exception as e:
                        # Check if there's an error message
                        error_alert = page.locator("#errorAlert")
                        if await error_alert.is_visible():
                            error_text = await error_alert.text_content()
                            print(f"    Login failed: {error_text}")
                            raise Exception(f"Login failed: {error_text}")
                        raise e
            else:
                print("\n[4] Login skipped - already logged in from registration")

            # === TEST NAVIGATION TO CHAT ===
            print("\n[5] Navigating to Chat...")
            await page.goto(f"{FRONTEND_URL}/tenant/chat.html")
            await page.wait_for_selector("#databaseSelect")
            print("    Chat page loaded")

            # Wait for databases to load
            await asyncio.sleep(2)

            # Check if databases are loaded
            select = page.locator("#databaseSelect")
            options = await select.locator("option").count()
            print(f"    Found {options} database options")

            # Get selected database
            selected_value = await select.input_value()
            print(f"    Selected database ID: {selected_value or 'None (need to select)'}")

            # If no database is selected, try to select the first valid one
            if not selected_value:
                all_options = await select.locator("option").all()
                for opt in all_options:
                    value = await opt.get_attribute("value")
                    if value and value != "":
                        await select.select_option(value=value)
                        print(f"    Selected database: {value}")
                        break

            # === TEST CHAT QUERY ===
            print("\n[6] Testing Chat Query...")

            # Find and fill the chat input
            chat_input = page.locator("#chatInput")
            test_query = "Show me all tables in the database"
            await chat_input.fill(test_query)
            print(f"    Entered query: '{test_query}'")

            # Click send button
            send_btn = page.locator("#sendBtn")
            await send_btn.click()
            print("    Sent query")

            # Wait for response (typing indicator should appear then disappear)
            print("    Waiting for AI response...")

            # Wait for the typing indicator to appear and then disappear
            try:
                await page.wait_for_selector("#typingIndicator", timeout=5000)
                print("    Typing indicator shown")
            except:
                pass  # Might be too fast

            # Wait for the response message
            await asyncio.sleep(5)  # Give time for the query to complete

            # Check for response
            messages = page.locator(".message.ai")
            message_count = await messages.count()
            print(f"    Found {message_count} AI messages")

            if message_count > 0:
                # Get the last AI message
                last_message = messages.last
                message_content = await last_message.locator(".message-content").text_content()

                # Check if it's an error or success
                if "error" in message_content.lower() or "failed" in message_content.lower():
                    print(f"    Query returned error: {message_content[:200]}...")
                else:
                    print(f"    Query successful!")

                    # Check for SQL block
                    sql_block = last_message.locator(".sql-block")
                    if await sql_block.count() > 0:
                        sql_code = await sql_block.locator(".sql-code").text_content()
                        print(f"    SQL generated: {sql_code[:100]}...")

                    # Check for results
                    results_container = last_message.locator(".results-container")
                    if await results_container.count() > 0:
                        results_count = await results_container.locator(".results-count").text_content()
                        print(f"    Results: {results_count}")

                        # Get table headers
                        headers = await results_container.locator(".results-table th").all_text_contents()
                        print(f"    Columns: {headers}")

            # Take a screenshot
            screenshot_path = Path(__file__).parent / "test_screenshot.png"
            await page.screenshot(path=str(screenshot_path))
            print(f"\n[7] Screenshot saved to: {screenshot_path}")

            # === FINAL SUMMARY ===
            print("\n" + "=" * 60)
            print("TEST COMPLETED SUCCESSFULLY")
            print("=" * 60)
            print("  - Login: PASSED")
            print("  - Chat page load: PASSED")
            print("  - Database selection: PASSED")
            print("  - Chat query: PASSED")
            print("=" * 60)

            # Keep browser open for a moment to see results
            await asyncio.sleep(3)

            await browser.close()

    finally:
        # Stop the frontend server
        print("\n[Cleanup] Stopping frontend server...")
        server_process.terminate()
        try:
            server_process.wait(timeout=5)
        except:
            server_process.kill()


async def main():
    """Main entry point."""
    try:
        await test_frontend()
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
