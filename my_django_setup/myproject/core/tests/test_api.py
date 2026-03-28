from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from core.models import (
    BOMNode,
    Customer,
    DesignBlockTemplate,
    DesignSupportRequest,
    InventoryItem,
    Machine,
    ManufacturingPlan,
    ManufacturingStep,
    Part,
    PermissionGrant,
    Quote,
    QuoteLine,
    UserProfile,
    WarehouseLocation,
    WorkOrder,
    WorkOrderStep,
)
from core.models.base import UserRole


class APISetupMixin:
    def setUp(self):
        self.user = User.objects.create_user("apiuser", password="apipass")
        self.admin_user = User.objects.create_superuser("admin", password="adminpass")
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin_user)
        self.customer = Customer.objects.create(
            company_name="API Corp", email="api@test.com",
            created_by=self.admin_user, updated_by=self.admin_user
        )


class CustomerAPITest(APISetupMixin, TestCase):
    def test_list_customers(self):
        resp = self.client.get("/api/v1/customers/")
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(resp.data["count"], 1)

    def test_create_customer(self):
        resp = self.client.post("/api/v1/customers/", {
            "company_name": "New Co", "email": "new@co.com"
        })
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data["company_name"], "New Co")

    def test_customer_scoping_for_customer_role(self):
        customer_user = User.objects.create_user("custuser", password="pass")
        UserProfile.objects.create(user=customer_user, role=UserRole.CUSTOMER, customer=self.customer)
        other_cust = Customer.objects.create(company_name="Other", email="o@o.com")
        client = APIClient()
        client.force_authenticate(user=customer_user)
        resp = client.get("/api/v1/customers/")
        self.assertEqual(resp.data["count"], 1)
        self.assertEqual(resp.data["results"][0]["company_name"], "API Corp")


class QuoteAPITest(APISetupMixin, TestCase):
    def test_create_quote(self):
        resp = self.client.post("/api/v1/quotes/", {
            "quote_number": "Q-API-001",
            "customer": str(self.customer.id),
            "title": "Test Quote",
        })
        self.assertEqual(resp.status_code, 201)

    def test_list_quotes(self):
        Quote.objects.create(quote_number="Q-LIST", customer=self.customer)
        resp = self.client.get("/api/v1/quotes/")
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(resp.data["count"], 1)

    def test_quote_transition(self):
        q = Quote.objects.create(
            quote_number="Q-TRANS-API", customer=self.customer,
            created_by=self.admin_user, updated_by=self.admin_user
        )
        resp = self.client.post(f"/api/v1/quotes/{q.id}/transition/", {
            "to_state": "in_review", "note": "Ready"
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["state"], "in_review")

    def test_quote_recalculate(self):
        q = Quote.objects.create(
            quote_number="Q-RECALC", customer=self.customer,
            created_by=self.admin_user, updated_by=self.admin_user
        )
        resp = self.client.post(f"/api/v1/quotes/{q.id}/recalculate/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("total", resp.data)

    def test_snapshot_version(self):
        q = Quote.objects.create(
            quote_number="Q-SNAP-API", customer=self.customer,
            created_by=self.admin_user, updated_by=self.admin_user
        )
        resp = self.client.post(f"/api/v1/quotes/{q.id}/snapshot-version/")
        self.assertEqual(resp.status_code, 201)
        self.assertIn("version_number", resp.data)

    def test_compare_versions(self):
        q = Quote.objects.create(
            quote_number="Q-CMP", customer=self.customer,
            created_by=self.admin_user, updated_by=self.admin_user
        )
        self.client.post(f"/api/v1/quotes/{q.id}/snapshot-version/")
        q.title = "Updated"
        q.save()
        self.client.post(f"/api/v1/quotes/{q.id}/snapshot-version/")
        resp = self.client.get(f"/api/v1/quotes/{q.id}/compare-versions/?left=1&right=2")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("left", resp.data)
        self.assertIn("right", resp.data)

    def test_generate_work_order(self):
        q = Quote.objects.create(
            quote_number="Q-GEN-WO", customer=self.customer,
            state=Quote.QuoteState.APPROVED,
            created_by=self.admin_user, updated_by=self.admin_user
        )
        resp = self.client.post(f"/api/v1/quotes/{q.id}/generate-work-order/")
        self.assertEqual(resp.status_code, 201)


class ManufacturingAPITest(APISetupMixin, TestCase):
    def test_create_plan(self):
        resp = self.client.post("/api/v1/manufacturing-plans/", {"name": "API Plan"})
        self.assertEqual(resp.status_code, 201)

    def test_create_step(self):
        plan = ManufacturingPlan.objects.create(name="Step Plan")
        resp = self.client.post("/api/v1/manufacturing-steps/", {
            "plan": str(plan.id), "sequence": 1, "machine_type": "laser"
        })
        self.assertEqual(resp.status_code, 201)

    def test_estimate_resources(self):
        plan = ManufacturingPlan.objects.create(name="Est Plan")
        ManufacturingStep.objects.create(plan=plan, sequence=1, machine_type="laser", processing_time_minutes=60)
        resp = self.client.post(f"/api/v1/manufacturing-plans/{plan.id}/estimate-resources/")
        self.assertEqual(resp.status_code, 201)
        self.assertIn("required_machine_hours", resp.data)

    def test_design_blocks_crud(self):
        resp = self.client.post("/api/v1/design-blocks/", {
            "name": "Laser Cut Block", "default_machine_type": "laser"
        })
        self.assertEqual(resp.status_code, 201)
        block_id = resp.data["id"]
        resp = self.client.get(f"/api/v1/design-blocks/{block_id}/")
        self.assertEqual(resp.status_code, 200)


class MachineAPITest(APISetupMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.machine = Machine.objects.create(
            identifier="M-API", name="API Machine", machine_type="laser"
        )

    def test_set_state(self):
        resp = self.client.post(f"/api/v1/machines/{self.machine.id}/set-state/", {
            "state": "busy"
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["state"], "busy")

    def test_utilization(self):
        resp = self.client.get(f"/api/v1/machines/{self.machine.id}/utilization/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("utilization_pct", resp.data)

    def test_invalid_state(self):
        resp = self.client.post(f"/api/v1/machines/{self.machine.id}/set-state/", {
            "state": "invalid_state"
        })
        self.assertEqual(resp.status_code, 400)


class WorkOrderAPITest(APISetupMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.plan = ManufacturingPlan.objects.create(name="WO API Plan")
        ManufacturingStep.objects.create(
            plan=self.plan, sequence=1, machine_type="laser", title="Cut",
            processing_time_minutes=60, setup_time_minutes=15
        )
        self.quote = Quote.objects.create(
            quote_number="Q-WO-API", customer=self.customer,
            state=Quote.QuoteState.APPROVED,
            preliminary_manufacturing_plan=self.plan,
            created_by=self.admin_user, updated_by=self.admin_user
        )
        from core.services import create_work_order_from_quote
        self.wo = create_work_order_from_quote(self.quote, self.admin_user)
        Machine.objects.create(identifier="LASER-API", name="Laser", machine_type="laser")

    def test_list_work_orders(self):
        resp = self.client.get("/api/v1/work-orders/")
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(resp.data["count"], 1)

    def test_auto_schedule(self):
        resp = self.client.post(f"/api/v1/work-orders/{self.wo.id}/auto-schedule/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("scheduled", resp.data)

    def test_generate_pick_list(self):
        resp = self.client.post(f"/api/v1/work-orders/{self.wo.id}/generate-pick-list/")
        self.assertEqual(resp.status_code, 201)
        self.assertIn("code", resp.data)

    def test_step_start_complete(self):
        step = self.wo.steps.first()
        resp = self.client.post(f"/api/v1/work-order-steps/{step.id}/start/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "in_progress")

        resp = self.client.post(f"/api/v1/work-order-steps/{step.id}/complete/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "completed")

    def test_step_block(self):
        step = self.wo.steps.first()
        resp = self.client.post(f"/api/v1/work-order-steps/{step.id}/block/", {
            "issue": "Material defect"
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "blocked")


class WarehouseAPITest(APISetupMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.loc = WarehouseLocation.objects.create(code="WH-API")
        self.item = InventoryItem.objects.create(
            sku="WH-SKU", name="Steel Sheet", location=self.loc, quantity=100
        )

    def test_list_inventory(self):
        resp = self.client.get("/api/v1/inventory-items/")
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(resp.data["count"], 1)

    def test_adjust_stock(self):
        resp = self.client.post(f"/api/v1/inventory-items/{self.item.id}/adjust/", {
            "quantity_delta": "-10",
            "movement_type": "outbound",
            "reference": "Test adjustment"
        })
        self.assertEqual(resp.status_code, 200)
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, Decimal("90"))

    def test_locations(self):
        resp = self.client.get("/api/v1/warehouse-locations/")
        self.assertEqual(resp.status_code, 200)


class QualityReportAPITest(APISetupMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.quote = Quote.objects.create(
            quote_number="Q-QC", customer=self.customer,
            state=Quote.QuoteState.APPROVED,
            created_by=self.admin_user, updated_by=self.admin_user
        )
        from core.services import create_work_order_from_quote
        self.wo = create_work_order_from_quote(self.quote, self.admin_user)

    def test_create_quality_report(self):
        step = self.wo.steps.first()
        resp = self.client.post("/api/v1/quality-reports/", {
            "work_order_step": str(step.id),
            "result": "pass",
            "inspection_notes": "All good"
        })
        self.assertEqual(resp.status_code, 201)


class NotificationAPITest(APISetupMixin, TestCase):
    def test_list_notifications(self):
        resp = self.client.get("/api/v1/notifications/")
        self.assertEqual(resp.status_code, 200)


class AuditLogAPITest(APISetupMixin, TestCase):
    def test_list_audit_log(self):
        resp = self.client.get("/api/v1/audit-log/")
        self.assertEqual(resp.status_code, 200)


class PermissionAPITest(APISetupMixin, TestCase):
    def test_create_permission(self):
        resp = self.client.post("/api/v1/permissions/", {
            "role": "sales", "entity": "Quote",
            "can_read": True, "can_write": True,
            "can_approve": False, "can_delete": False
        })
        self.assertEqual(resp.status_code, 201)


class UnauthenticatedAccessTest(TestCase):
    def test_requires_auth(self):
        client = APIClient()
        resp = client.get("/api/v1/customers/")
        self.assertEqual(resp.status_code, 403)
