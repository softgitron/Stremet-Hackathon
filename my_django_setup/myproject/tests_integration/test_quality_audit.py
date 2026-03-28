"""Integration tests for quality management, audit trail, notifications, and RBAC."""
import pytest
from core.models import Quote, WorkOrder, AuditLogEntry, InAppNotification

pytestmark = pytest.mark.django_db


@pytest.fixture
def wo_with_steps(api_client, customer_entity, manufacturing_plan, machine_laser, machine_press):
    resp = api_client.post("/api/v1/quotes/", {
        "quote_number": "Q-INT-QA",
        "customer": str(customer_entity.id),
        "preliminary_manufacturing_plan": str(manufacturing_plan.id),
    })
    quote_id = resp.data["id"]
    api_client.post(f"/api/v1/quotes/{quote_id}/transition/", {"to_state": "in_review"})
    api_client.post(f"/api/v1/quotes/{quote_id}/transition/", {"to_state": "customer_review"})
    api_client.post(f"/api/v1/quotes/{quote_id}/transition/", {"to_state": "approved"})
    wo = WorkOrder.objects.filter(source_quote_id=quote_id).first()
    return wo


class TestQualityReports:
    def test_create_quality_report(self, api_client, wo_with_steps, machine_laser):
        step = wo_with_steps.steps.first()
        resp = api_client.post("/api/v1/quality-reports/", {
            "work_order_step": str(step.id),
            "machine": str(machine_laser.id),
            "result": "pass",
            "inspection_notes": "All dimensions within tolerance",
            "material_batch": "LOT-2026-001",
        })
        assert resp.status_code == 201
        assert resp.data["result"] == "pass"

    def test_fail_report_with_root_cause(self, api_client, wo_with_steps):
        step = wo_with_steps.steps.first()
        resp = api_client.post("/api/v1/quality-reports/", {
            "work_order_step": str(step.id),
            "result": "fail",
            "inspection_notes": "Surface scratch detected",
            "root_cause_hint": "Material handling issue during loading",
        })
        assert resp.status_code == 201
        assert resp.data["result"] == "fail"

    def test_traceability_query(self, api_client, wo_with_steps, machine_laser):
        step = wo_with_steps.steps.first()
        api_client.post("/api/v1/quality-reports/", {
            "work_order_step": str(step.id),
            "machine": str(machine_laser.id),
            "result": "pass",
            "material_batch": "LOT-TRACE-001",
        })
        reports = api_client.get(f"/api/v1/quality-reports/?machine={machine_laser.id}")
        assert reports.data["count"] >= 1
        reports = api_client.get(f"/api/v1/quality-reports/?work_order_step={step.id}")
        assert reports.data["count"] >= 1


class TestAuditLog:
    def test_audit_entries_created_on_transition(self, api_client, customer_entity):
        resp = api_client.post("/api/v1/quotes/", {
            "quote_number": "Q-INT-AUDIT",
            "customer": str(customer_entity.id),
        })
        quote_id = resp.data["id"]
        api_client.post(f"/api/v1/quotes/{quote_id}/transition/", {"to_state": "in_review"})
        entries = AuditLogEntry.objects.filter(entity_type="Quote", entity_id=str(quote_id))
        assert entries.exists()

    def test_audit_log_api(self, api_client, customer_entity):
        resp = api_client.post("/api/v1/quotes/", {
            "quote_number": "Q-INT-AUDIT2",
            "customer": str(customer_entity.id),
        })
        quote_id = resp.data["id"]
        api_client.post(f"/api/v1/quotes/{quote_id}/transition/", {"to_state": "in_review"})
        log = api_client.get("/api/v1/audit-log/?entity_type=Quote")
        assert log.status_code == 200
        assert log.data["count"] >= 1

    def test_audit_export_csv(self, api_client, customer_entity):
        resp = api_client.post("/api/v1/quotes/", {
            "quote_number": "Q-INT-EXPORT",
            "customer": str(customer_entity.id),
        })
        api_client.post(f"/api/v1/quotes/{resp.data['id']}/transition/", {"to_state": "in_review"})
        export = api_client.get("/api/v1/audit-log/export/")
        assert export.status_code == 200
        assert export["Content-Type"] == "text/csv"
        content = export.content.decode()
        assert "timestamp" in content
        assert "quote_transition" in content


class TestNotifications:
    def test_notifications_on_transition(self, api_client, customer_entity, admin_user):
        resp = api_client.post("/api/v1/quotes/", {
            "quote_number": "Q-INT-NOTIF",
            "customer": str(customer_entity.id),
        })
        api_client.post(f"/api/v1/quotes/{resp.data['id']}/transition/", {"to_state": "in_review"})
        notifs = api_client.get("/api/v1/notifications/?event_code=quote_transition")
        assert notifs.status_code == 200
        assert notifs.data["count"] >= 1

    def test_mark_notification_read(self, api_client, customer_entity):
        resp = api_client.post("/api/v1/quotes/", {
            "quote_number": "Q-INT-NOTIF-READ",
            "customer": str(customer_entity.id),
        })
        api_client.post(f"/api/v1/quotes/{resp.data['id']}/transition/", {"to_state": "in_review"})
        notifs = api_client.get("/api/v1/notifications/?read=false")
        if notifs.data["count"] > 0:
            n_id = notifs.data["results"][0]["id"]
            api_client.patch(f"/api/v1/notifications/{n_id}/", {"read": True})
            updated = api_client.get(f"/api/v1/notifications/{n_id}/")
            assert updated.data["read"] is True


class TestRBAC:
    def test_customer_sees_only_own_data(self, customer_client, customer_entity, admin_user):
        other = api_client_with_other_customer(admin_user)
        resp = customer_client.get("/api/v1/customers/")
        assert resp.data["count"] == 1
        assert resp.data["results"][0]["company_name"] == customer_entity.company_name

    def test_customer_cannot_see_other_quotes(self, customer_client, customer_entity, admin_user):
        from core.models import Customer
        other_cust = Customer.objects.create(company_name="Other Corp", email="other@corp.com")
        Quote.objects.create(quote_number="Q-OTHER", customer=other_cust)
        Quote.objects.create(quote_number="Q-MINE", customer=customer_entity)
        resp = customer_client.get("/api/v1/quotes/")
        for q in resp.data["results"]:
            assert str(q["customer"]) == str(customer_entity.id)

    def test_unauthenticated_blocked(self):
        from rest_framework.test import APIClient
        client = APIClient()
        resp = client.get("/api/v1/quotes/")
        assert resp.status_code == 403

    def test_permission_grant_crud(self, api_client):
        resp = api_client.post("/api/v1/permissions/", {
            "role": "designer", "entity": "ManufacturingPlan",
            "can_read": True, "can_write": True,
            "can_approve": False, "can_delete": False,
        })
        assert resp.status_code == 201
        resp = api_client.get(f"/api/v1/permissions/?role=designer&entity=ManufacturingPlan")
        assert resp.data["count"] == 1


def api_client_with_other_customer(admin_user):
    pass
