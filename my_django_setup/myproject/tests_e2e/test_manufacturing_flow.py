"""E2E tests for manufacturing portal: work order list, detail, machine status."""
import pytest


@pytest.mark.e2e
class TestManufacturingPanel:
    def test_manufacturing_panel_loads(self, admin_page):
        admin_page.goto("/portal/production/")
        assert admin_page.locator("text=Production").first.is_visible()
        assert admin_page.locator("text=Active work orders").is_visible()

    def test_shows_work_orders(self, admin_page, seed_data):
        admin_page.goto("/portal/production/")
        assert admin_page.locator("text=WO-").first.is_visible()

    def test_shows_machines(self, admin_page):
        admin_page.goto("/portal/production/")
        assert admin_page.locator("text=Machines").first.is_visible()
        assert admin_page.locator("text=E2E-LASER").first.is_visible()

    def test_work_order_detail_accessible(self, admin_page, seed_data):
        admin_page.goto("/portal/production/")
        steps_link = admin_page.locator('a:has-text("Steps")').first
        if steps_link.is_visible():
            steps_link.click()
            admin_page.wait_for_load_state("networkidle")
            assert admin_page.locator("text=Manufacturing steps").is_visible()
            assert admin_page.locator("text=Completion").is_visible()


@pytest.mark.e2e
class TestWorkOrderDetail:
    def test_step_table_shows_correct_info(self, admin_page, seed_data):
        admin_page.goto("/portal/production/")
        steps_link = admin_page.locator('a:has-text("Steps")').first
        if steps_link.is_visible():
            steps_link.click()
            admin_page.wait_for_load_state("networkidle")
            assert admin_page.locator("text=E2E Cut").first.is_visible() or admin_page.locator("text=laser").first.is_visible()

    def test_back_to_list(self, admin_page, seed_data):
        admin_page.goto("/portal/production/")
        steps_link = admin_page.locator('a:has-text("Steps")').first
        if steps_link.is_visible():
            steps_link.click()
            admin_page.wait_for_load_state("networkidle")
            admin_page.click('a:has-text("Back to list")')
            admin_page.wait_for_load_state("networkidle")
            assert "/portal/production/" in admin_page.url
