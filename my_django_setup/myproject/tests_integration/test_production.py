"""Integration tests for production execution: work orders, scheduling, step tracking."""
import pytest
from decimal import Decimal
from core.models import Quote, WorkOrder, WorkOrderStep, ScheduledStep, PickList

pytestmark = pytest.mark.django_db


@pytest.fixture
def approved_quote_and_wo(api_client, customer_entity, manufacturing_plan, machine_laser, machine_press):
    resp = api_client.post("/api/v1/quotes/", {
        "quote_number": "Q-INT-PROD",
        "customer": str(customer_entity.id),
        "title": "Production Test",
        "preliminary_manufacturing_plan": str(manufacturing_plan.id),
    })
    quote_id = resp.data["id"]
    api_client.post(f"/api/v1/quotes/{quote_id}/recalculate/")
    api_client.post(f"/api/v1/quotes/{quote_id}/transition/", {"to_state": "in_review"})
    api_client.post(f"/api/v1/quotes/{quote_id}/transition/", {"to_state": "customer_review"})
    api_client.post(f"/api/v1/quotes/{quote_id}/transition/", {"to_state": "approved"})
    wo = WorkOrder.objects.filter(source_quote_id=quote_id).first()
    return quote_id, wo


class TestWorkOrderGeneration:
    def test_work_order_created_with_steps(self, approved_quote_and_wo):
        quote_id, wo = approved_quote_and_wo
        assert wo is not None
        assert wo.steps.count() == 2
        assert wo.snapshot["quote_number"] == "Q-INT-PROD"

    def test_snapshot_is_immutable(self, approved_quote_and_wo):
        _, wo = approved_quote_and_wo
        original_snapshot = wo.snapshot.copy()
        quote = Quote.objects.get(pk=wo.source_quote_id)
        quote.title = "Changed after WO"
        quote.save()
        wo.refresh_from_db()
        assert wo.snapshot == original_snapshot

    def test_generate_work_order_idempotent(self, approved_quote_and_wo, api_client):
        quote_id, wo = approved_quote_and_wo
        resp = api_client.post(f"/api/v1/quotes/{quote_id}/generate-work-order/")
        assert resp.status_code == 201
        assert resp.data["id"] == str(wo.id)


class TestScheduling:
    def test_auto_schedule_assigns_machines(self, approved_quote_and_wo, api_client):
        _, wo = approved_quote_and_wo
        resp = api_client.post(f"/api/v1/work-orders/{wo.id}/auto-schedule/")
        assert resp.status_code == 200
        assert resp.data["scheduled"] >= 1

        for step in wo.steps.all():
            step.refresh_from_db()
            if step.machine:
                assert step.status == WorkOrderStep.ExecutionStatus.READY
                assert step.planned_start is not None
                assert step.planned_end is not None

    def test_manual_schedule_override(self, approved_quote_and_wo, api_client, machine_laser):
        _, wo = approved_quote_and_wo
        step = wo.steps.first()
        from django.utils import timezone
        from datetime import timedelta
        now = timezone.now()
        resp = api_client.post("/api/v1/scheduled-steps/", {
            "work_order_step": str(step.id),
            "machine": str(machine_laser.id),
            "planned_start": now.isoformat(),
            "planned_end": (now + timedelta(hours=2)).isoformat(),
            "manual_override": True,
        })
        assert resp.status_code == 201
        assert resp.data["manual_override"] is True


class TestStepExecution:
    def test_start_stop_workflow(self, approved_quote_and_wo, api_client):
        _, wo = approved_quote_and_wo
        step = wo.steps.order_by("sequence").first()

        start = api_client.post(f"/api/v1/work-order-steps/{step.id}/start/")
        assert start.status_code == 200
        assert start.data["status"] == "in_progress"
        assert start.data["actual_start"] is not None

        complete = api_client.post(f"/api/v1/work-order-steps/{step.id}/complete/")
        assert complete.status_code == 200
        assert complete.data["status"] == "completed"
        assert complete.data["actual_end"] is not None

        wo.refresh_from_db()
        assert wo.completion_percent > Decimal("0")

    def test_block_with_issue(self, approved_quote_and_wo, api_client):
        _, wo = approved_quote_and_wo
        step = wo.steps.order_by("sequence").first()

        block = api_client.post(f"/api/v1/work-order-steps/{step.id}/block/", {
            "issue": "Material defect detected on sheet #45",
        })
        assert block.status_code == 200
        assert block.data["status"] == "blocked"
        assert "Material defect" in block.data["issue_log"]

    def test_cannot_start_completed_step(self, approved_quote_and_wo, api_client):
        _, wo = approved_quote_and_wo
        step = wo.steps.order_by("sequence").first()
        api_client.post(f"/api/v1/work-order-steps/{step.id}/start/")
        api_client.post(f"/api/v1/work-order-steps/{step.id}/complete/")
        start_again = api_client.post(f"/api/v1/work-order-steps/{step.id}/start/")
        assert start_again.status_code == 400

    def test_completion_percentage_updates(self, approved_quote_and_wo, api_client):
        _, wo = approved_quote_and_wo
        steps = list(wo.steps.order_by("sequence"))

        for s in steps:
            api_client.post(f"/api/v1/work-order-steps/{s.id}/start/")
            api_client.post(f"/api/v1/work-order-steps/{s.id}/complete/")

        wo.refresh_from_db()
        assert wo.completion_percent == Decimal("100.00")


class TestPickLists:
    def test_generate_pick_list(self, approved_quote_and_wo, api_client):
        _, wo = approved_quote_and_wo
        resp = api_client.post(f"/api/v1/work-orders/{wo.id}/generate-pick-list/")
        assert resp.status_code == 201
        assert resp.data["code"].startswith("PL-")

        lines = api_client.get(f"/api/v1/pick-list-lines/?pick_list={resp.data['id']}")
        assert lines.data["count"] >= 1

    def test_pick_list_idempotent(self, approved_quote_and_wo, api_client):
        _, wo = approved_quote_and_wo
        r1 = api_client.post(f"/api/v1/work-orders/{wo.id}/generate-pick-list/")
        r2 = api_client.post(f"/api/v1/work-orders/{wo.id}/generate-pick-list/")
        assert r1.data["id"] == r2.data["id"]


class TestDelayTracking:
    def test_delay_report(self, approved_quote_and_wo, api_client):
        _, wo = approved_quote_and_wo
        resp = api_client.get(f"/api/v1/work-orders/{wo.id}/delays/")
        assert resp.status_code == 200
        assert "step_delays" in resp.data
        assert resp.data["wo_number"] == wo.wo_number
