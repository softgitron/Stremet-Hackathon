"""E2E tests for portal navigation and dashboard KPIs."""
import pytest


@pytest.mark.e2e
class TestHomeAndNavigation:
    def test_home_dashboard_loads(self, admin_page):
        admin_page.goto("/")
        assert admin_page.title() == "Stremet | Portals"
        assert admin_page.locator("text=Stremet").first.is_visible()
        cards = admin_page.locator(".kpi-card")
        assert cards.count() >= 6

    def test_navbar_links_work(self, admin_page):
        admin_page.goto("/")
        for link_text, expected_url_part in [
            ("Sales", "/portal/sales/"),
            ("Design", "/portal/design/"),
            ("Customer", "/portal/customer/"),
            ("Manufacturing", "/portal/production/"),
            ("Warehouse", "/portal/warehouse/"),
            ("Ops admin", "/portal/ops/"),
        ]:
            admin_page.click(f'nav >> text="{link_text}"')
            admin_page.wait_for_load_state("networkidle")
            assert expected_url_part in admin_page.url


@pytest.mark.e2e
class TestSalesPortal:
    def test_sales_portal_shows_kpis(self, admin_page):
        admin_page.goto("/portal/sales/")
        assert admin_page.locator("text=Sales workspace").is_visible()
        assert admin_page.locator("text=Quotes total").is_visible()
        assert admin_page.locator("text=Open design requests").is_visible()
        assert admin_page.locator("text=Approved revenue").is_visible()

    def test_sales_portal_shows_quotes_table(self, admin_page, seed_data):
        admin_page.goto("/portal/sales/")
        assert admin_page.locator(f"text={seed_data['quote_number']}").first.is_visible()

    def test_sales_portal_shows_design_requests(self, admin_page):
        admin_page.goto("/portal/sales/")
        assert admin_page.locator("text=Design support requests").is_visible()


@pytest.mark.e2e
class TestDesignPortal:
    def test_design_portal_shows_plans(self, admin_page):
        admin_page.goto("/portal/design/")
        assert admin_page.locator("text=Manufacturing plans").first.is_visible()
        assert admin_page.locator("text=E2E Plan").first.is_visible()

    def test_design_portal_shows_blocks(self, admin_page):
        admin_page.goto("/portal/design/")
        assert admin_page.locator("text=Reusable design blocks").is_visible()
        assert admin_page.locator("text=E2E Laser Block").is_visible()

    def test_design_portal_shows_requests(self, admin_page):
        admin_page.goto("/portal/design/")
        assert admin_page.locator("text=Design support requests").is_visible()


@pytest.mark.e2e
class TestWarehousePortal:
    def test_warehouse_shows_inventory(self, admin_page):
        admin_page.goto("/portal/warehouse/")
        assert admin_page.locator("text=Inventory items").is_visible()
        assert admin_page.locator("text=E2E-STL").is_visible()

    def test_warehouse_shows_locations(self, admin_page):
        admin_page.goto("/portal/warehouse/")
        assert admin_page.locator("text=Storage locations").first.is_visible()
        assert admin_page.locator("text=E2E-A01").first.is_visible()


@pytest.mark.e2e
class TestAdminPortal:
    def test_admin_shows_system_kpis(self, admin_page):
        admin_page.goto("/portal/ops/")
        assert admin_page.locator("text=Operations overview").is_visible()
        assert admin_page.locator("text=Machine fleet").is_visible()
        assert admin_page.locator("text=Recent audit log").is_visible()

    def test_admin_shows_machine_stats(self, admin_page):
        admin_page.goto("/portal/ops/")
        assert admin_page.locator("text=Available").is_visible()
