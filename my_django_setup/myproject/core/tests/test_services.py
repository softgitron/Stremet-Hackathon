from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from core.models import (
    AuditLogEntry,
    BOMNode,
    Customer,
    CustomerOrder,
    InAppNotification,
    InventoryItem,
    Machine,
    ManufacturingPlan,
    ManufacturingStep,
    PickList,
    PickListLine,
    Quote,
    QuoteCostBreakdown,
    QuoteStateTransition,
    QuoteVersion,
    ResourceEstimate,
    ScheduledStep,
    StockMovement,
    UserProfile,
    WarehouseLocation,
    WorkOrder,
    WorkOrderStep,
)
from core.models.base import UserRole
from core.services import (
    auto_schedule_work_order,
    build_quote_snapshot,
    compute_quote_cost,
    compute_resource_estimate,
    create_pick_list_from_work_order,
    create_work_order_from_quote,
    log_audit,
    mark_design_change_for_quote,
    reserve_materials_for_step,
    save_quote_version,
    transition_quote,
)


class QuoteSnapshotTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("snap_user", password="pass")
        self.customer = Customer.objects.create(company_name="SnapCo", email="s@s.com")
        self.quote = Quote.objects.create(
            quote_number="Q-SNAP", customer=self.customer, title="Snap Test"
        )

    def test_basic_snapshot(self):
        snap = build_quote_snapshot(self.quote)
        self.assertEqual(snap["quote_number"], "Q-SNAP")
        self.assertEqual(snap["lines"], [])
        self.assertIsNone(snap["manufacturing_plan"])

    def test_snapshot_with_plan(self):
        plan = ManufacturingPlan.objects.create(name="Plan S")
        ManufacturingStep.objects.create(plan=plan, sequence=1, machine_type="laser", title="Cut")
        self.quote.preliminary_manufacturing_plan = plan
        self.quote.save()
        snap = build_quote_snapshot(self.quote)
        self.assertIsNotNone(snap["manufacturing_plan"])
        self.assertEqual(len(snap["manufacturing_plan"]["steps"]), 1)


class QuoteVersionTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ver_user", password="pass")
        self.customer = Customer.objects.create(company_name="VerCo", email="v@v.com")
        self.quote = Quote.objects.create(
            quote_number="Q-VER", customer=self.customer
        )

    def test_version_numbering(self):
        v1 = save_quote_version(self.quote, self.user)
        self.assertEqual(v1.version_number, 1)
        v2 = save_quote_version(self.quote, self.user)
        self.assertEqual(v2.version_number, 2)

    def test_version_snapshot_content(self):
        v = save_quote_version(self.quote, self.user)
        self.assertEqual(v.snapshot["quote_number"], "Q-VER")


class QuoteTransitionTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("trans_user", password="pass")
        UserProfile.objects.create(user=self.user, role=UserRole.SALES)
        self.customer = Customer.objects.create(company_name="TransCo", email="t@t.com")
        self.quote = Quote.objects.create(
            quote_number="Q-TRANS", customer=self.customer
        )

    def test_valid_transition(self):
        result = transition_quote(self.quote, "in_review", self.user, note="Ready for review")
        self.assertEqual(result.state, "in_review")
        self.assertEqual(QuoteStateTransition.objects.filter(quote=self.quote).count(), 1)

    def test_invalid_transition_raises(self):
        with self.assertRaises(ValueError):
            transition_quote(self.quote, "approved", self.user)

    def test_same_state_noop(self):
        result = transition_quote(self.quote, "draft", self.user)
        self.assertEqual(result.state, "draft")
        self.assertEqual(QuoteStateTransition.objects.filter(quote=self.quote).count(), 0)

    def test_full_lifecycle(self):
        transition_quote(self.quote, "in_review", self.user)
        transition_quote(self.quote, "customer_review", self.user)
        transition_quote(self.quote, "approved", self.user)
        self.quote.refresh_from_db()
        self.assertEqual(self.quote.state, "approved")
        self.assertTrue(WorkOrder.objects.filter(source_quote=self.quote).exists())

    def test_audit_log_created(self):
        transition_quote(self.quote, "in_review", self.user)
        entries = AuditLogEntry.objects.filter(entity_type="Quote", entity_id=str(self.quote.id))
        self.assertTrue(entries.exists())

    def test_notification_sent(self):
        transition_quote(self.quote, "in_review", self.user)
        notifs = InAppNotification.objects.filter(event_code="quote_transition")
        self.assertTrue(notifs.exists())


class CostCalculationTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("cost_user", password="pass")
        self.customer = Customer.objects.create(company_name="CostCo", email="c@c.com")
        self.loc = WarehouseLocation.objects.create(code="COST-LOC")
        self.item = InventoryItem.objects.create(
            sku="STL-COST", name="Steel", location=self.loc,
            quantity=1000, unit_cost=Decimal("5.00")
        )
        self.plan = ManufacturingPlan.objects.create(name="Cost Plan")
        ManufacturingStep.objects.create(
            plan=self.plan, sequence=1, machine_type="laser",
            processing_time_minutes=60, setup_time_minutes=15
        )
        BOMNode.objects.create(
            manufacturing_plan=self.plan, inventory_item=self.item,
            quantity=10, unit="sheets"
        )
        self.quote = Quote.objects.create(
            quote_number="Q-COST", customer=self.customer,
            preliminary_manufacturing_plan=self.plan
        )

    def test_cost_calculation(self):
        breakdown = compute_quote_cost(self.quote, self.user)
        self.assertIsInstance(breakdown, QuoteCostBreakdown)
        self.assertGreater(breakdown.material_cost, Decimal("0"))
        self.assertGreater(breakdown.machine_time_cost, Decimal("0"))
        self.assertGreater(breakdown.total, Decimal("0"))

    def test_reproducibility(self):
        b1 = compute_quote_cost(self.quote, self.user)
        b2 = compute_quote_cost(self.quote, self.user)
        self.assertEqual(b1.total, b2.total)

    def test_clears_recalculation_flag(self):
        self.quote.needs_recalculation = True
        self.quote.save()
        compute_quote_cost(self.quote, self.user)
        self.quote.refresh_from_db()
        self.assertFalse(self.quote.needs_recalculation)

    def test_material_cost_from_bom(self):
        breakdown = compute_quote_cost(self.quote, self.user)
        self.assertEqual(breakdown.material_cost, Decimal("50.0000"))

    def test_inputs_stored(self):
        breakdown = compute_quote_cost(self.quote, self.user)
        self.assertIn("lines", breakdown.inputs)
        self.assertIn("machine_minutes", breakdown.inputs)


class WorkOrderCreationTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("wo_user", password="pass")
        UserProfile.objects.create(user=self.user, role=UserRole.SALES)
        self.customer = Customer.objects.create(company_name="WOCo", email="w@w.com")
        self.plan = ManufacturingPlan.objects.create(name="WO Plan")
        ManufacturingStep.objects.create(plan=self.plan, sequence=1, machine_type="laser", title="Cut")
        ManufacturingStep.objects.create(plan=self.plan, sequence=2, machine_type="press", title="Bend")
        self.quote = Quote.objects.create(
            quote_number="Q-WO", customer=self.customer,
            preliminary_manufacturing_plan=self.plan
        )

    def test_creates_work_order_on_approval(self):
        transition_quote(self.quote, "in_review", self.user)
        transition_quote(self.quote, "customer_review", self.user)
        transition_quote(self.quote, "approved", self.user)
        wo = WorkOrder.objects.filter(source_quote=self.quote).first()
        self.assertIsNotNone(wo)
        self.assertEqual(wo.steps.count(), 2)

    def test_idempotent(self):
        self.quote.state = Quote.QuoteState.APPROVED
        self.quote.save()
        wo1 = create_work_order_from_quote(self.quote, self.user)
        wo2 = create_work_order_from_quote(self.quote, self.user)
        self.assertEqual(wo1.pk, wo2.pk)

    def test_snapshot_immutable(self):
        self.quote.state = Quote.QuoteState.APPROVED
        self.quote.save()
        wo = create_work_order_from_quote(self.quote, self.user)
        self.assertIn("quote_number", wo.snapshot)

    def test_customer_order_created(self):
        self.quote.state = Quote.QuoteState.APPROVED
        self.quote.save()
        create_work_order_from_quote(self.quote, self.user)
        self.assertTrue(CustomerOrder.objects.filter(source_quote=self.quote).exists())


class ResourceEstimateTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("est_user", password="pass")
        self.plan = ManufacturingPlan.objects.create(name="Est Plan")
        ManufacturingStep.objects.create(
            plan=self.plan, sequence=1, machine_type="laser",
            processing_time_minutes=120, setup_time_minutes=30
        )
        self.loc = WarehouseLocation.objects.create(code="EST-LOC")
        self.item = InventoryItem.objects.create(
            sku="EST-MAT", name="Material", location=self.loc, quantity=500
        )
        BOMNode.objects.create(
            manufacturing_plan=self.plan, inventory_item=self.item, quantity=20
        )

    def test_estimate_created(self):
        est = compute_resource_estimate(self.plan, self.user)
        self.assertIsInstance(est, ResourceEstimate)
        self.assertGreater(est.required_machine_hours, Decimal("0"))
        self.assertGreater(est.required_labor_hours, Decimal("0"))

    def test_material_requirements_populated(self):
        est = compute_resource_estimate(self.plan, self.user)
        self.assertEqual(len(est.material_requirements), 1)
        self.assertEqual(est.material_requirements[0]["sku"], "EST-MAT")


class SchedulingTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("sched_user", password="pass")
        UserProfile.objects.create(user=self.user, role=UserRole.SALES)
        self.customer = Customer.objects.create(company_name="SchedCo", email="sc@s.com")
        self.plan = ManufacturingPlan.objects.create(name="Sched Plan")
        ManufacturingStep.objects.create(
            plan=self.plan, sequence=1, machine_type="laser",
            processing_time_minutes=60, setup_time_minutes=15, title="Cut"
        )
        self.quote = Quote.objects.create(
            quote_number="Q-SCHED", customer=self.customer,
            preliminary_manufacturing_plan=self.plan
        )
        Machine.objects.create(identifier="LASER-1", name="Laser", machine_type="laser")
        self.quote.state = Quote.QuoteState.APPROVED
        self.quote.save()
        self.wo = create_work_order_from_quote(self.quote, self.user)

    def test_auto_schedule(self):
        results = auto_schedule_work_order(self.wo, self.user)
        self.assertGreater(len(results), 0)
        step = self.wo.steps.first()
        self.assertEqual(step.status, WorkOrderStep.ExecutionStatus.READY)
        self.assertIsNotNone(step.machine)


class PickListTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("pl_user", password="pass")
        UserProfile.objects.create(user=self.user, role=UserRole.SALES)
        self.customer = Customer.objects.create(company_name="PLCo", email="pl@p.com")
        self.loc = WarehouseLocation.objects.create(code="PL-LOC")
        self.item = InventoryItem.objects.create(
            sku="PL-MAT", name="Material", location=self.loc, quantity=100
        )
        self.plan = ManufacturingPlan.objects.create(name="PL Plan")
        ManufacturingStep.objects.create(plan=self.plan, sequence=1, machine_type="laser")
        BOMNode.objects.create(
            manufacturing_plan=self.plan, inventory_item=self.item, quantity=5
        )
        self.quote = Quote.objects.create(
            quote_number="Q-PL", customer=self.customer,
            preliminary_manufacturing_plan=self.plan
        )
        self.quote.state = Quote.QuoteState.APPROVED
        self.quote.save()
        self.wo = create_work_order_from_quote(self.quote, self.user)

    def test_create_pick_list(self):
        pl = create_pick_list_from_work_order(self.wo, self.user)
        self.assertIsNotNone(pl)
        self.assertEqual(pl.lines.count(), 1)

    def test_idempotent(self):
        pl1 = create_pick_list_from_work_order(self.wo, self.user)
        pl2 = create_pick_list_from_work_order(self.wo, self.user)
        self.assertEqual(pl1.pk, pl2.pk)


class DesignChangeRecalcTest(TestCase):
    def test_marks_quotes_for_recalc(self):
        customer = Customer.objects.create(company_name="DC", email="dc@d.com")
        plan = ManufacturingPlan.objects.create(name="DC Plan")
        q = Quote.objects.create(
            quote_number="Q-DC", customer=customer,
            preliminary_manufacturing_plan=plan, needs_recalculation=False
        )
        mark_design_change_for_quote(plan.id)
        q.refresh_from_db()
        self.assertTrue(q.needs_recalculation)


class AuditLogTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("audit_user", password="pass")

    def test_log_audit(self):
        log_audit(
            user=self.user,
            action="test_action",
            entity_type="TestEntity",
            entity_id="123",
            after={"key": "value"},
        )
        entry = AuditLogEntry.objects.filter(action="test_action").first()
        self.assertIsNotNone(entry)
        self.assertEqual(entry.entity_type, "TestEntity")
