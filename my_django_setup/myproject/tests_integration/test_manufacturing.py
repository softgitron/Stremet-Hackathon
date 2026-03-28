"""Integration tests for manufacturing design, planning, and design blocks."""
import pytest
from core.models import ManufacturingPlan, ManufacturingStep, ResourceEstimate

pytestmark = pytest.mark.django_db


class TestManufacturingPlanCRUD:
    def test_create_plan_with_steps(self, api_client):
        plan = api_client.post("/api/v1/manufacturing-plans/", {"name": "INT Plan A"})
        assert plan.status_code == 201
        plan_id = plan.data["id"]

        s1 = api_client.post("/api/v1/manufacturing-steps/", {
            "plan": plan_id, "sequence": 1, "machine_type": "laser",
            "title": "Cut outline", "processing_time_minutes": 45, "setup_time_minutes": 10,
        })
        assert s1.status_code == 201

        s2 = api_client.post("/api/v1/manufacturing-steps/", {
            "plan": plan_id, "sequence": 2, "machine_type": "press",
            "title": "Bend flanges", "processing_time_minutes": 30, "setup_time_minutes": 5,
        })
        assert s2.status_code == 201

        steps = api_client.get(f"/api/v1/manufacturing-steps/?plan={plan_id}")
        assert steps.data["count"] == 2

    def test_step_with_io_materials(self, api_client, inventory_item):
        plan = api_client.post("/api/v1/manufacturing-plans/", {"name": "INT IO Plan"})
        plan_id = plan.data["id"]
        step = api_client.post("/api/v1/manufacturing-steps/", {
            "plan": plan_id, "sequence": 1, "machine_type": "laser",
        })
        step_id = step.data["id"]

        inp = api_client.post("/api/v1/step-inputs/", {
            "step": step_id, "inventory_item": str(inventory_item.id),
            "quantity": 5, "unit": "sheets",
        })
        assert inp.status_code == 201

    def test_step_artifacts(self, api_client):
        plan = api_client.post("/api/v1/manufacturing-plans/", {"name": "INT Artifact Plan"})
        step = api_client.post("/api/v1/manufacturing-steps/", {
            "plan": plan.data["id"], "sequence": 1, "machine_type": "laser",
        })
        artifact = api_client.post("/api/v1/step-artifacts/", {
            "step": step.data["id"], "kind": "sop",
            "text_content": "1. Load sheet\n2. Align to fixture\n3. Start program",
        })
        assert artifact.status_code == 201
        assert artifact.data["kind"] == "sop"


class TestResourceEstimation:
    def test_estimate_resources(self, api_client, manufacturing_plan):
        resp = api_client.post(f"/api/v1/manufacturing-plans/{manufacturing_plan.id}/estimate-resources/")
        assert resp.status_code == 201
        assert float(resp.data["required_machine_hours"]) > 0
        assert float(resp.data["required_labor_hours"]) > 0
        assert len(resp.data["material_requirements"]) == 2

    def test_estimate_updates_plan_time(self, api_client, manufacturing_plan):
        api_client.post(f"/api/v1/manufacturing-plans/{manufacturing_plan.id}/estimate-resources/")
        plan = ManufacturingPlan.objects.get(pk=manufacturing_plan.id)
        assert plan.estimated_total_time_minutes > 0


class TestDesignBlocks:
    def test_create_and_use_template(self, api_client):
        block = api_client.post("/api/v1/design-blocks/", {
            "name": "INT Template Block",
            "description": "Reusable laser cutting step",
            "default_machine_type": "laser",
            "default_parameters": {"power_kw": 4, "speed": 3000},
            "version_tag": "1.0.0",
        }, format="json")
        assert block.status_code == 201

        plan = api_client.post("/api/v1/manufacturing-plans/", {"name": "INT Block Plan"})
        step = api_client.post("/api/v1/manufacturing-steps/", {
            "plan": plan.data["id"], "sequence": 1,
            "machine_type": "laser", "template_block": block.data["id"],
        })
        assert step.status_code == 201
        assert str(step.data["template_block"]) == str(block.data["id"])

    def test_version_control_blocks(self, api_client):
        block = api_client.post("/api/v1/design-blocks/", {
            "name": "INT Versioned Block",
            "version_tag": "1.0.0",
        })
        api_client.patch(f"/api/v1/design-blocks/{block.data['id']}/", {
            "version_tag": "1.1.0",
            "default_parameters": {"updated": True},
        }, format="json")
        updated = api_client.get(f"/api/v1/design-blocks/{block.data['id']}/")
        assert updated.data["version_tag"] == "1.1.0"


class TestBOMManagement:
    def test_hierarchical_bom(self, api_client, manufacturing_plan, inventory_item):
        nodes = api_client.get(f"/api/v1/bom-nodes/?manufacturing_plan={manufacturing_plan.id}")
        assert nodes.data["count"] == 2

        parent_id = nodes.data["results"][0]["id"]
        child = api_client.post("/api/v1/bom-nodes/", {
            "manufacturing_plan": str(manufacturing_plan.id),
            "inventory_item": str(inventory_item.id),
            "quantity": 2, "unit": "pcs", "sequence": 3,
            "parent": parent_id,
        })
        assert child.status_code == 201
        assert str(child.data["parent"]) == str(parent_id)

    def test_bom_change_triggers_recalc_flag(self, api_client, customer_entity, manufacturing_plan, inventory_item):
        from core.models import Quote
        q = Quote.objects.create(
            quote_number="Q-INT-BOM-RECALC", customer=customer_entity,
            preliminary_manufacturing_plan=manufacturing_plan,
            needs_recalculation=False,
        )
        existing_nodes = api_client.get(f"/api/v1/bom-nodes/?manufacturing_plan={manufacturing_plan.id}")
        if existing_nodes.data["count"] > 0:
            node_id = existing_nodes.data["results"][0]["id"]
            api_client.patch(f"/api/v1/bom-nodes/{node_id}/", {"quantity": 99})
            q.refresh_from_db()
            assert q.needs_recalculation is True
