import uuid

from django.contrib.auth.models import User
from django.test import TestCase

from core.models import (
    BOMNode,
    Customer,
    CustomerOrder,
    DesignBlockTemplate,
    DesignSupportRequest,
    InventoryItem,
    Machine,
    MachineMaintenanceWindow,
    ManufacturingPlan,
    ManufacturingStep,
    Part,
    PermissionGrant,
    PickList,
    Quote,
    QuoteAttachment,
    QuoteComment,
    QuoteCostBreakdown,
    QuoteDiscussionThread,
    QuoteLine,
    QuoteStateTransition,
    QuoteVersion,
    StepArtifact,
    StepInputMaterial,
    StepOutputPart,
    StoredFile,
    UserProfile,
    WarehouseLocation,
    WorkOrder,
    WorkOrderStep,
)
from core.models.base import UserRole


class BaseEntityTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("testuser", password="pass")
        self.customer = Customer.objects.create(
            company_name="Acme", email="acme@test.com", created_by=self.user, updated_by=self.user
        )

    def test_uuid_primary_key(self):
        self.assertIsInstance(self.customer.pk, uuid.UUID)

    def test_revision_increments_on_save(self):
        initial = self.customer.revision
        self.customer.company_name = "Acme 2"
        self.customer.save()
        self.assertEqual(self.customer.revision, initial + 1)

    def test_audit_fields(self):
        self.assertIsNotNone(self.customer.created_at)
        self.assertIsNotNone(self.customer.updated_at)
        self.assertEqual(self.customer.created_by, self.user)


class CustomerModelTest(TestCase):
    def test_str(self):
        c = Customer(company_name="Test Corp")
        self.assertEqual(str(c), "Test Corp")


class PartModelTest(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(company_name="Acme", email="a@b.com")
        self.part = Part.objects.create(customer=self.customer, name="Bracket-A")

    def test_str(self):
        self.assertEqual(str(self.part), "Bracket-A")


class QuoteModelTest(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(company_name="QC Corp", email="q@c.com")
        self.quote = Quote.objects.create(
            quote_number="Q-001", customer=self.customer, title="Test Quote"
        )

    def test_default_state(self):
        self.assertEqual(self.quote.state, Quote.QuoteState.DRAFT)

    def test_str(self):
        self.assertIn("Q-001", str(self.quote))

    def test_needs_recalculation_default(self):
        self.assertFalse(self.quote.needs_recalculation)


class QuoteLineTest(TestCase):
    def setUp(self):
        c = Customer.objects.create(company_name="T", email="t@t.com")
        self.quote = Quote.objects.create(quote_number="Q-LINE", customer=c)
        self.line = QuoteLine.objects.create(
            quote=self.quote, description="Steel plate", quantity=10, unit_price=5
        )

    def test_line_total_property(self):
        self.assertEqual(self.line.line_total, 50)


class MachineModelTest(TestCase):
    def test_default_state(self):
        m = Machine.objects.create(identifier="M-001", name="Laser Cutter", machine_type="laser")
        self.assertEqual(m.state, Machine.MachineState.AVAILABLE)

    def test_states(self):
        self.assertIn("available", dict(Machine.MachineState.choices))
        self.assertIn("busy", dict(Machine.MachineState.choices))
        self.assertIn("maintenance", dict(Machine.MachineState.choices))
        self.assertIn("offline", dict(Machine.MachineState.choices))


class ManufacturingPlanTest(TestCase):
    def test_create_with_steps(self):
        plan = ManufacturingPlan.objects.create(name="Plan A")
        ManufacturingStep.objects.create(
            plan=plan, sequence=1, machine_type="laser", title="Cut"
        )
        ManufacturingStep.objects.create(
            plan=plan, sequence=2, machine_type="press", title="Bend"
        )
        self.assertEqual(plan.steps.count(), 2)


class DesignBlockTemplateTest(TestCase):
    def test_str_with_version(self):
        b = DesignBlockTemplate.objects.create(
            name="Laser Cut", version_tag="2.0.0"
        )
        self.assertIn("2.0.0", str(b))


class WarehouseModelTest(TestCase):
    def test_location_hierarchy(self):
        parent = WarehouseLocation.objects.create(code="A")
        child = WarehouseLocation.objects.create(code="A-01", parent=parent)
        self.assertEqual(child.parent, parent)
        self.assertIn(child, parent.children.all())

    def test_inventory_item_statuses(self):
        loc = WarehouseLocation.objects.create(code="B")
        item = InventoryItem.objects.create(
            sku="STL-001", name="Steel Sheet", location=loc, quantity=100
        )
        self.assertEqual(item.status, InventoryItem.InventoryStatus.AVAILABLE)


class UserProfileTest(TestCase):
    def test_role_choices(self):
        roles = dict(UserRole.choices)
        self.assertIn("customer", roles)
        self.assertIn("sales", roles)
        self.assertIn("designer", roles)
        self.assertIn("manufacturer", roles)
        self.assertIn("warehouse", roles)
        self.assertIn("administrator", roles)

    def test_profile_str(self):
        user = User.objects.create_user("profuser", password="pass")
        profile = UserProfile.objects.create(user=user, role=UserRole.SALES)
        self.assertIn("profuser", str(profile))
        self.assertIn("Sales", str(profile))


class PermissionGrantTest(TestCase):
    def test_unique_together(self):
        PermissionGrant.objects.create(
            role="sales", entity="Quote", can_read=True, can_write=True
        )
        with self.assertRaises(Exception):
            PermissionGrant.objects.create(
                role="sales", entity="Quote", can_read=True, can_write=False
            )


class WorkOrderStepStatusTest(TestCase):
    def test_execution_statuses(self):
        statuses = dict(WorkOrderStep.ExecutionStatus.choices)
        for expected in ("pending", "ready", "in_progress", "completed", "blocked"):
            self.assertIn(expected, statuses)
