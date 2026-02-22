from playwright.sync_api import sync_playwright

def run(playwright):
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page()

    # Mock the API response
    def handle_attachments(route):
        print(f"Intercepted: {route.request.url}")
        route.fulfill(
            status=200,
            content_type="application/json",
            body='[{"id":"1","filename":"test.pdf","file_size":1024,"scan_status":"clean","quarantined":false,"uploaded_by_user_id":"u1","created_at":"2023-01-01T00:00:00Z"}]'
        )

    # Intercept API calls
    page.route("**/attachments/surrogates/test-id/attachments*", handle_attachments)

    # Navigate to the test page
    try:
        response = page.goto("http://localhost:3000/test-upload-zone")
        print(f"Navigated to test page: {response.status}")
    except Exception as e:
        print(f"Navigation failed: {e}")
        browser.close()
        return

    # Wait for the list to appear
    try:
        page.wait_for_selector("ul.space-y-2", timeout=5000)
        print("List appeared")
    except Exception as e:
        print(f"List did not appear: {e}")
        # Take screenshot of error state
        page.screenshot(path="verification/error.png")

    # Verify accessibility attributes
    dropzone = page.locator('[aria-label="File upload zone"]')
    if dropzone.count() > 0:
        print("Dropzone found with aria-label")
    else:
        print("Dropzone NOT found with aria-label")

    list_element = page.locator("ul.space-y-2")
    if list_element.count() > 0:
        print("Semantic list found")
    else:
        print("Semantic list NOT found")

    # Screenshot
    page.screenshot(path="verification/file_upload_zone.png")

    browser.close()

with sync_playwright() as playwright:
    run(playwright)
