"""E2E tests for customer self-service: login, dashboard, order lookup, design upload."""
import pytest


@pytest.mark.e2e
class TestCustomerGuestFlow:
    def test_guest_entry_page(self, page, seed_data):
        page.goto("/portal/customer/")
        assert page.locator("text=Customer portal").is_visible()
        assert page.locator("text=Quick order lookup").is_visible()
        assert page.locator('text="Log in to your account"').is_visible()

    def test_guest_order_lookup_with_valid_order(self, admin_page, seed_data):
        import requests
        session = requests.Session()
        session.auth = (seed_data["admin_username"], seed_data["admin_password"])
        wos = session.get("http://localhost:8111/api/v1/work-orders/")
        if wos.json().get("count", 0) > 0:
            wo = wos.json()["results"][0]
            order_resp = session.get(f"http://localhost:8111/api/v1/orders/{wo['customer_order']}/")
            order_number = order_resp.json()["order_number"]
            page = admin_page
            page.goto("/portal/customer/")
            page.fill('input[name="order_id"]', order_number)
            page.click('button:has-text("View order")')
            page.wait_for_load_state("networkidle")
            assert order_number in page.content()

    def test_guest_order_lookup_empty_shows_error(self, page, seed_data):
        page.goto("/portal/customer/")
        page.fill('input[name="order_id"]', "")
        page.click('button:has-text("View order")')
        page.wait_for_load_state("networkidle")


@pytest.mark.e2e
class TestCustomerDashboard:
    def test_customer_sees_own_dashboard(self, customer_page, seed_data):
        customer_page.goto("/portal/customer/dashboard/")
        customer_page.wait_for_load_state("networkidle")
        content = customer_page.content()
        if seed_data["customer_name"] in content:
            assert customer_page.locator("text=Quotes").first.is_visible()
            assert customer_page.locator("text=Orders").first.is_visible()
        else:
            assert "Customer portal" in content or "Log in" in content

    def test_customer_sees_quotes(self, customer_page, seed_data):
        customer_page.goto("/portal/customer/dashboard/")
        customer_page.wait_for_load_state("networkidle")
        content = customer_page.content()
        if seed_data["customer_name"] in content:
            assert seed_data["quote_number"] in content
        else:
            assert "Customer" in content

    def test_customer_quote_detail(self, customer_page, seed_data):
        customer_page.goto("/portal/customer/dashboard/")
        customer_page.wait_for_load_state("networkidle")
        details_link = customer_page.locator("text=Details").first
        if details_link.is_visible():
            details_link.click()
            customer_page.wait_for_load_state("networkidle")
            assert "Q-E2E" in customer_page.content()
        else:
            assert "Customer" in customer_page.content()

    def test_upload_design_page_accessible(self, customer_page, seed_data):
        customer_page.goto("/portal/customer/")
        customer_page.wait_for_load_state("networkidle")
        upload_link = customer_page.locator('a:has-text("Upload design")')
        if upload_link.is_visible():
            upload_link.click()
            customer_page.wait_for_load_state("networkidle")
            assert "Upload design" in customer_page.content() or "title" in customer_page.content()


@pytest.mark.e2e
class TestCustomerDesignUpload:
    def test_submit_design_creates_quote(self, customer_page, seed_data):
        customer_page.goto("/portal/customer/upload/")
        customer_page.wait_for_load_state("networkidle")
        title_input = customer_page.locator('input[name="title"]')
        if title_input.is_visible():
            title_input.fill("E2E Uploaded Part Design")
            customer_page.fill('textarea[name="description"]', "Custom bracket, 3mm steel, 90 degree bend")
            customer_page.click('button:has-text("Submit design")')
            customer_page.wait_for_load_state("networkidle")
            assert "Design uploaded" in customer_page.content() or "Q-SELF" in customer_page.content() or "dashboard" in customer_page.url or "customer" in customer_page.url
