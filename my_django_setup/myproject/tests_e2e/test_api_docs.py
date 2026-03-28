"""E2E tests for API documentation and schema accessibility."""
import pytest


@pytest.mark.e2e
class TestAPIDocumentation:
    def test_swagger_ui_loads(self, page, seed_data):
        page.goto("/api/v1/docs/")
        page.wait_for_load_state("networkidle")
        assert page.locator("text=Stremet Manufacturing API").is_visible()

    def test_openapi_schema_downloadable(self, page, seed_data):
        response = page.request.get("/api/v1/schema/?format=json")
        assert response.status == 200
        data = response.json()
        assert "paths" in data
        assert len(data["paths"]) > 80

    def test_api_requires_authentication(self, page, seed_data):
        response = page.request.get("/api/v1/customers/")
        assert response.status == 403
