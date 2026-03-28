"""Integration tests for the full quote lifecycle: create → review → approve → work order."""
import pytest
from core.models import Quote, QuoteStateTransition, QuoteVersion, WorkOrder, CustomerOrder, AuditLogEntry

pytestmark = pytest.mark.django_db


class TestQuoteCreationAndVersioning:
    def test_create_quote_with_lines(self, api_client, customer_entity):
        resp = api_client.post("/api/v1/quotes/", {
            "quote_number": "Q-INT-001",
            "customer": str(customer_entity.id),
            "title": "Integration Test Quote",
            "currency": "EUR",
        })
        assert resp.status_code == 201
        quote_id = resp.data["id"]

        resp = api_client.post("/api/v1/quote-lines/", {
            "quote": quote_id,
            "description": "Steel panel 100x200mm",
            "quantity": "50",
            "unit_price": "15.00",
        })
        assert resp.status_code == 201

        resp = api_client.post("/api/v1/quote-lines/", {
            "quote": quote_id,
            "description": "Mounting hardware",
            "quantity": "100",
            "unit_price": "2.50",
        })
        assert resp.status_code == 201

        resp = api_client.get(f"/api/v1/quotes/{quote_id}/")
        assert resp.status_code == 200
        assert len(resp.data["lines"]) == 2
        assert resp.data["state"] == "draft"

    def test_version_snapshot_on_create(self, api_client, customer_entity):
        resp = api_client.post("/api/v1/quotes/", {
            "quote_number": "Q-INT-VER",
            "customer": str(customer_entity.id),
            "title": "Versioning Test",
        })
        quote_id = resp.data["id"]
        versions = api_client.get(f"/api/v1/quote-versions/?quote={quote_id}")
        assert versions.data["count"] >= 1

    def test_manual_snapshot_creates_new_version(self, api_client, customer_entity):
        resp = api_client.post("/api/v1/quotes/", {
            "quote_number": "Q-INT-SNAP",
            "customer": str(customer_entity.id),
            "title": "Snapshot Test",
        })
        quote_id = resp.data["id"]
        snap = api_client.post(f"/api/v1/quotes/{quote_id}/snapshot-version/")
        assert snap.status_code == 201
        assert snap.data["version_number"] == 2

    def test_compare_versions(self, api_client, customer_entity):
        resp = api_client.post("/api/v1/quotes/", {
            "quote_number": "Q-INT-CMP",
            "customer": str(customer_entity.id),
            "title": "Compare V1",
        })
        quote_id = resp.data["id"]
        api_client.patch(f"/api/v1/quotes/{quote_id}/", {"title": "Compare V2"})
        cmp = api_client.get(f"/api/v1/quotes/{quote_id}/compare-versions/?left=1&right=2")
        assert cmp.status_code == 200
        assert cmp.data["left"]["title"] == "Compare V1"
        assert cmp.data["right"]["title"] == "Compare V2"


class TestQuoteTransitions:
    def test_valid_draft_to_in_review(self, api_client, customer_entity):
        resp = api_client.post("/api/v1/quotes/", {
            "quote_number": "Q-INT-TR1",
            "customer": str(customer_entity.id),
            "title": "Transition Test",
        })
        quote_id = resp.data["id"]
        tr = api_client.post(f"/api/v1/quotes/{quote_id}/transition/", {
            "to_state": "in_review",
            "note": "Ready for sales review",
        })
        assert tr.status_code == 200
        assert tr.data["state"] == "in_review"
        transitions = QuoteStateTransition.objects.filter(quote_id=quote_id)
        assert transitions.count() == 1

    def test_invalid_transition_blocked(self, api_client, customer_entity):
        resp = api_client.post("/api/v1/quotes/", {
            "quote_number": "Q-INT-TR2",
            "customer": str(customer_entity.id),
        })
        quote_id = resp.data["id"]
        tr = api_client.post(f"/api/v1/quotes/{quote_id}/transition/", {
            "to_state": "approved",
        })
        assert tr.status_code == 400

    def test_full_approval_lifecycle(self, api_client, customer_entity, manufacturing_plan):
        resp = api_client.post("/api/v1/quotes/", {
            "quote_number": "Q-INT-FULL",
            "customer": str(customer_entity.id),
            "title": "Full Lifecycle",
            "preliminary_manufacturing_plan": str(manufacturing_plan.id),
        })
        quote_id = resp.data["id"]

        api_client.post(f"/api/v1/quotes/{quote_id}/recalculate/")

        api_client.post(f"/api/v1/quotes/{quote_id}/transition/", {"to_state": "in_review"})
        api_client.post(f"/api/v1/quotes/{quote_id}/transition/", {"to_state": "customer_review"})
        api_client.post(f"/api/v1/quotes/{quote_id}/transition/", {"to_state": "approved", "note": "Customer approved"})

        quote = Quote.objects.get(pk=quote_id)
        assert quote.state == "approved"
        assert WorkOrder.objects.filter(source_quote=quote).exists()
        assert CustomerOrder.objects.filter(source_quote=quote).exists()

    def test_rejection_is_terminal(self, api_client, customer_entity):
        resp = api_client.post("/api/v1/quotes/", {
            "quote_number": "Q-INT-REJ",
            "customer": str(customer_entity.id),
        })
        quote_id = resp.data["id"]
        api_client.post(f"/api/v1/quotes/{quote_id}/transition/", {"to_state": "in_review"})
        api_client.post(f"/api/v1/quotes/{quote_id}/transition/", {"to_state": "rejected"})
        tr = api_client.post(f"/api/v1/quotes/{quote_id}/transition/", {"to_state": "draft"})
        assert tr.status_code == 400


class TestQuoteCostCalculation:
    def test_cost_with_manufacturing_plan(self, api_client, customer_entity, manufacturing_plan):
        resp = api_client.post("/api/v1/quotes/", {
            "quote_number": "Q-INT-COST",
            "customer": str(customer_entity.id),
            "preliminary_manufacturing_plan": str(manufacturing_plan.id),
        })
        quote_id = resp.data["id"]
        cost = api_client.post(f"/api/v1/quotes/{quote_id}/recalculate/")
        assert cost.status_code == 200
        assert float(cost.data["material_cost"]) > 0
        assert float(cost.data["machine_time_cost"]) > 0
        assert float(cost.data["labor_cost"]) > 0
        assert float(cost.data["overhead_cost"]) > 0
        assert float(cost.data["total"]) > 0
        assert "lines" in cost.data["inputs"]

    def test_recalc_flag_cleared(self, api_client, customer_entity, manufacturing_plan):
        resp = api_client.post("/api/v1/quotes/", {
            "quote_number": "Q-INT-RECALC",
            "customer": str(customer_entity.id),
            "preliminary_manufacturing_plan": str(manufacturing_plan.id),
        })
        quote_id = resp.data["id"]
        api_client.post("/api/v1/quote-lines/", {
            "quote": quote_id, "description": "Test item", "quantity": 1, "unit_price": 10,
        })
        q = Quote.objects.get(pk=quote_id)
        assert q.needs_recalculation is True
        api_client.post(f"/api/v1/quotes/{quote_id}/recalculate/")
        q.refresh_from_db()
        assert q.needs_recalculation is False


class TestQuoteCollaboration:
    def test_threaded_discussion(self, api_client, customer_entity):
        qresp = api_client.post("/api/v1/quotes/", {
            "quote_number": "Q-INT-COLLAB",
            "customer": str(customer_entity.id),
        })
        quote_id = qresp.data["id"]
        thread = api_client.post("/api/v1/quote-threads/", {
            "quote": quote_id,
            "subject": "Material clarification",
        })
        assert thread.status_code == 201
        thread_id = thread.data["id"]

        c1 = api_client.post("/api/v1/quote-comments/", {
            "thread": thread_id,
            "body": "What material grade is required?",
            "author_role": "sales",
        })
        assert c1.status_code == 201

        c2 = api_client.post("/api/v1/quote-comments/", {
            "thread": thread_id,
            "body": "We need SS304 grade.",
            "author_role": "customer",
            "parent": c1.data["id"],
        })
        assert c2.status_code == 201

        comments = api_client.get(f"/api/v1/quote-comments/?thread={thread_id}")
        assert comments.data["count"] == 2

    def test_design_support_request(self, api_client, customer_entity):
        qresp = api_client.post("/api/v1/quotes/", {
            "quote_number": "Q-INT-DSR",
            "customer": str(customer_entity.id),
        })
        quote_id = qresp.data["id"]
        dsr = api_client.post("/api/v1/design-support/", {
            "quote": quote_id,
            "description": "Need manufacturing plan for custom bracket",
            "priority": "high",
        })
        assert dsr.status_code == 201
        assert dsr.data["status"] == "open"

        api_client.patch(f"/api/v1/design-support/{dsr.data['id']}/", {
            "status": "accepted",
            "designer_notes": "Will prepare plan within 2 days",
        })
        updated = api_client.get(f"/api/v1/design-support/{dsr.data['id']}/")
        assert updated.data["status"] == "accepted"
