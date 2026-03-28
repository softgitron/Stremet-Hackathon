from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone

from .models import (
    AuditLogEntry,
    CustomerOrder,
    InAppNotification,
    InventoryItem,
    Machine,
    ManufacturingPlan,
    PickList,
    PickListLine,
    Quote,
    QuoteCostBreakdown,
    QuoteStateTransition,
    QuoteVersion,
    ResourceEstimate,
    ScheduledStep,
    StockMovement,
    WorkOrder,
    WorkOrderStep,
)


def build_quote_snapshot(quote: Quote) -> dict[str, Any]:
    lines = [
        {
            "description": line.description,
            "quantity": str(line.quantity),
            "unit_price": str(line.unit_price),
            "part_id": str(line.part_id) if line.part_id else None,
        }
        for line in quote.lines.all()
    ]
    plan_data = None
    if quote.preliminary_manufacturing_plan_id:
        plan = quote.preliminary_manufacturing_plan
        plan_data = {
            "id": str(plan.id),
            "name": plan.name,
            "steps": [
                {
                    "id": str(s.id),
                    "sequence": s.sequence,
                    "machine_type": s.machine_type,
                    "title": s.title,
                    "processing_time_minutes": str(s.processing_time_minutes),
                    "setup_time_minutes": str(s.setup_time_minutes),
                    "status": s.status,
                }
                for s in plan.steps.all()
            ],
        }
    bom = []
    if quote.preliminary_manufacturing_plan_id:
        for node in quote.preliminary_manufacturing_plan.bom_nodes.all():
            bom.append(
                {
                    "id": str(node.id),
                    "inventory_sku": node.inventory_item.sku,
                    "quantity": str(node.quantity),
                    "unit": node.unit,
                }
            )
    cost = {}
    if hasattr(quote, "cost_breakdown") and quote.cost_breakdown:
        cb = quote.cost_breakdown
        cost = {
            "material": str(cb.material_cost),
            "machine_time": str(cb.machine_time_cost),
            "labor": str(cb.labor_cost),
            "overhead": str(cb.overhead_cost),
            "total": str(cb.total),
        }
    return {
        "quote_number": quote.quote_number,
        "state": quote.state,
        "title": quote.title,
        "lines": lines,
        "manufacturing_plan": plan_data,
        "bom": bom,
        "cost": cost,
        "currency": quote.currency,
        "total_price": str(quote.total_price),
    }


def save_quote_version(quote: Quote, user) -> QuoteVersion:
    last = quote.versions.order_by("-version_number").first()
    next_num = (last.version_number + 1) if last else 1
    snap = build_quote_snapshot(quote)
    return QuoteVersion.objects.create(
        quote=quote,
        version_number=next_num,
        snapshot=snap,
        created_by=user,
        updated_by=user,
    )


ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    Quote.QuoteState.DRAFT: {Quote.QuoteState.IN_REVIEW},
    Quote.QuoteState.IN_REVIEW: {
        Quote.QuoteState.CUSTOMER_REVIEW,
        Quote.QuoteState.DRAFT,
        Quote.QuoteState.REJECTED,
    },
    Quote.QuoteState.CUSTOMER_REVIEW: {
        Quote.QuoteState.APPROVED,
        Quote.QuoteState.REJECTED,
        Quote.QuoteState.IN_REVIEW,
    },
    Quote.QuoteState.APPROVED: {Quote.QuoteState.EXPIRED},
    Quote.QuoteState.REJECTED: set(),
    Quote.QuoteState.EXPIRED: set(),
}


def transition_quote(
    quote: Quote,
    to_state: str,
    user,
    note: str = "",
) -> Quote:
    if to_state == quote.state:
        return quote
    allowed = ALLOWED_TRANSITIONS.get(quote.state, set())
    if to_state not in allowed:
        raise ValueError(f"Cannot transition from {quote.state} to {to_state}")
    old = quote.state
    quote.state = to_state
    quote.updated_by = user
    quote.save()
    QuoteStateTransition.objects.create(
        quote=quote,
        from_state=old,
        to_state=to_state,
        user=user,
        note=note,
        created_by=user,
        updated_by=user,
    )
    save_quote_version(quote, user)
    log_audit(
        user=user,
        action="quote_transition",
        entity_type="Quote",
        entity_id=str(quote.id),
        before={"state": old},
        after={"state": to_state},
        metadata={"note": note},
    )
    _send_notification(
        user=user,
        title=f"Quote {quote.quote_number} moved to {quote.get_state_display()}",
        body=note,
        event_code="quote_transition",
        payload={"quote_id": str(quote.id), "state": to_state},
    )
    if to_state == Quote.QuoteState.APPROVED:
        create_work_order_from_quote(quote, user)
    return quote


def compute_quote_cost(quote: Quote, user, overhead_rate: Decimal | None = None) -> QuoteCostBreakdown:
    overhead_rate = overhead_rate or Decimal("0.15")
    material = Decimal("0")
    inputs_detail: dict[str, Any] = {"lines": []}
    if quote.preliminary_manufacturing_plan_id:
        for node in quote.preliminary_manufacturing_plan.bom_nodes.all():
            unit = node.inventory_item.unit_cost or Decimal("0")
            line_cost = node.quantity * unit
            material += line_cost
            inputs_detail["lines"].append(
                {
                    "sku": node.inventory_item.sku,
                    "qty": str(node.quantity),
                    "unit_cost": str(unit),
                    "line_cost": str(line_cost),
                }
            )
    machine_minutes = Decimal("0")
    if quote.preliminary_manufacturing_plan_id:
        for step in quote.preliminary_manufacturing_plan.steps.all():
            machine_minutes += step.processing_time_minutes + step.setup_time_minutes
    machine_rate = Decimal("2.50")
    machine_cost = machine_minutes * machine_rate
    labor_hours = machine_minutes / Decimal("60")
    labor_rate = Decimal("45.00")
    labor_cost = labor_hours * labor_rate
    subtotal = material + machine_cost + labor_cost
    overhead_cost = (subtotal * overhead_rate).quantize(Decimal("0.0001"))
    total = subtotal + overhead_cost
    inputs_detail.update(
        {
            "machine_minutes": str(machine_minutes),
            "machine_rate_per_min": str(machine_rate),
            "labor_rate_per_h": str(labor_rate),
            "overhead_rate": str(overhead_rate),
        }
    )
    breakdown, created = QuoteCostBreakdown.objects.get_or_create(
        quote=quote,
        defaults={
            "material_cost": material.quantize(Decimal("0.0001")),
            "machine_time_cost": machine_cost.quantize(Decimal("0.0001")),
            "labor_cost": labor_cost.quantize(Decimal("0.0001")),
            "overhead_cost": overhead_cost,
            "total": total.quantize(Decimal("0.0001")),
            "inputs": inputs_detail,
            "created_by": user,
            "updated_by": user,
        },
    )
    if not created:
        breakdown.material_cost = material.quantize(Decimal("0.0001"))
        breakdown.machine_time_cost = machine_cost.quantize(Decimal("0.0001"))
        breakdown.labor_cost = labor_cost.quantize(Decimal("0.0001"))
        breakdown.overhead_cost = overhead_cost
        breakdown.total = total.quantize(Decimal("0.0001"))
        breakdown.inputs = inputs_detail
        breakdown.updated_by = user
        breakdown.save()
    quote.total_price = total.quantize(Decimal("0.01"))
    quote.needs_recalculation = False
    quote.updated_by = user
    quote.save()
    return breakdown


def create_work_order_from_quote(quote: Quote, user) -> WorkOrder | None:
    if quote.state != Quote.QuoteState.APPROVED:
        return None
    existing = WorkOrder.objects.filter(source_quote=quote).first()
    if existing:
        return existing
    snap = build_quote_snapshot(quote)
    order = CustomerOrder.objects.filter(source_quote=quote).first()
    if not order:
        order = CustomerOrder.objects.create(
            source_quote=quote,
            customer=quote.customer,
            order_number=f"ORD-{quote.quote_number}",
            delivery_deadline=quote.valid_until,
            created_by=user,
            updated_by=user,
        )
    wo_number = f"WO-{quote.quote_number}"
    wo = WorkOrder.objects.create(
        wo_number=wo_number,
        customer_order=order,
        source_quote=quote,
        snapshot=snap,
        delivery_deadline=quote.valid_until,
        created_by=user,
        updated_by=user,
    )
    seq = 1
    if quote.preliminary_manufacturing_plan_id:
        for step in quote.preliminary_manufacturing_plan.steps.all().order_by("sequence"):
            WorkOrderStep.objects.create(
                work_order=wo,
                sequence=seq,
                snapshot_step_key=str(step.id),
                title=step.title or step.machine_type,
                machine_type=step.machine_type,
                status=WorkOrderStep.ExecutionStatus.PENDING,
                created_by=user,
                updated_by=user,
            )
            seq += 1
    else:
        WorkOrderStep.objects.create(
            work_order=wo,
            sequence=1,
            snapshot_step_key="generic",
            title="Production",
            machine_type="general",
            status=WorkOrderStep.ExecutionStatus.PENDING,
            created_by=user,
            updated_by=user,
        )
    _update_work_order_completion(wo)
    log_audit(
        user=user,
        action="work_order_created",
        entity_type="WorkOrder",
        entity_id=str(wo.id),
        after={"wo_number": wo.wo_number, "quote": str(quote.id)},
    )
    _send_notification(
        user=user,
        title=f"Work Order {wo.wo_number} created",
        body=f"From quote {quote.quote_number}",
        event_code="work_order_created",
        payload={"work_order_id": str(wo.id)},
    )
    return wo


def _update_work_order_completion(wo: WorkOrder) -> None:
    steps = list(wo.steps.all())
    if not steps:
        wo.completion_percent = Decimal("0")
        wo.save()
        return
    done = sum(1 for s in steps if s.status == WorkOrderStep.ExecutionStatus.COMPLETED)
    wo.completion_percent = (Decimal(done) / Decimal(len(steps)) * Decimal("100")).quantize(
        Decimal("0.01")
    )
    wo.save()


def mark_design_change_for_quote(plan_id: uuid.UUID | None) -> None:
    if not plan_id:
        return
    qs = Quote.objects.filter(preliminary_manufacturing_plan_id=plan_id)
    qs.update(needs_recalculation=True, updated_at=timezone.now())


@transaction.atomic
def log_audit(
    *,
    user,
    action: str,
    entity_type: str,
    entity_id: str,
    before: dict | None = None,
    after: dict | None = None,
    metadata: dict | None = None,
):
    AuditLogEntry.objects.create(
        user=user if user and hasattr(user, "pk") else None,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before=before,
        after=after,
        metadata=metadata or {},
    )


def _send_notification(
    *,
    user,
    title: str,
    body: str = "",
    event_code: str = "",
    payload: dict | None = None,
):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    from .models import UserProfile

    profiles = UserProfile.objects.filter(
        role__in=["administrator", "sales", "manufacturer"]
    ).select_related("user")
    recipients = {p.user for p in profiles if p.user_id}
    if user and hasattr(user, "pk"):
        recipients.add(user)
    for r in recipients:
        InAppNotification.objects.create(
            recipient=r,
            title=title,
            body=body,
            event_code=event_code,
            payload=payload or {},
            created_by=user if hasattr(user, "pk") else None,
            updated_by=user if hasattr(user, "pk") else None,
        )


def compute_resource_estimate(plan: ManufacturingPlan, user) -> ResourceEstimate:
    machine_hours = Decimal("0")
    for step in plan.steps.all():
        machine_hours += (step.processing_time_minutes + step.setup_time_minutes) / Decimal("60")
    labor_hours = machine_hours * Decimal("1.2")
    material_reqs = []
    for node in plan.bom_nodes.select_related("inventory_item").all():
        material_reqs.append({
            "sku": node.inventory_item.sku,
            "name": node.inventory_item.name,
            "quantity_required": str(node.quantity),
            "unit": node.unit,
            "available": str(node.inventory_item.quantity),
        })
    est = ResourceEstimate.objects.create(
        manufacturing_plan=plan,
        required_machine_hours=machine_hours.quantize(Decimal("0.0001")),
        required_labor_hours=labor_hours.quantize(Decimal("0.0001")),
        material_requirements=material_reqs,
        created_by=user,
        updated_by=user,
    )
    plan.estimated_total_time_minutes = (machine_hours * 60).quantize(Decimal("0.01"))
    plan.save(update_fields=["estimated_total_time_minutes", "updated_at"])
    return est


def auto_schedule_work_order(wo: WorkOrder, user) -> list[ScheduledStep]:
    results = []
    now = timezone.now()
    cursor = now
    for step in wo.steps.order_by("sequence"):
        machine = Machine.objects.filter(
            machine_type=step.machine_type,
            state=Machine.MachineState.AVAILABLE,
        ).first()
        if not machine:
            machine = Machine.objects.filter(
                state=Machine.MachineState.AVAILABLE
            ).first()
        if not machine:
            continue
        snap_data = wo.snapshot.get("manufacturing_plan") or {}
        step_data = {}
        for s in snap_data.get("steps", []):
            if s.get("id") == step.snapshot_step_key:
                step_data = s
                break
        proc_mins = Decimal(step_data.get("processing_time_minutes", "60"))
        setup_mins = Decimal(step_data.get("setup_time_minutes", "15"))
        from datetime import timedelta
        total_mins = proc_mins + setup_mins
        end = cursor + timedelta(minutes=float(total_mins))
        sched = ScheduledStep.objects.create(
            work_order_step=step,
            machine=machine,
            planned_start=cursor,
            planned_end=end,
            created_by=user,
            updated_by=user,
        )
        step.machine = machine
        step.planned_start = cursor
        step.planned_end = end
        step.status = WorkOrderStep.ExecutionStatus.READY
        step.save()
        results.append(sched)
        cursor = end
    return results


def reserve_materials_for_step(step: WorkOrderStep, user) -> None:
    snap = step.work_order.snapshot
    for bom_entry in snap.get("bom", []):
        item = InventoryItem.objects.filter(sku=bom_entry.get("inventory_sku")).first()
        if not item:
            continue
        qty = Decimal(bom_entry.get("quantity", "0"))
        per_step = qty / max(step.work_order.steps.count(), 1)
        if item.quantity >= per_step:
            item.quantity -= per_step
            item.status = InventoryItem.InventoryStatus.RESERVED
            item.save()
            StockMovement.objects.create(
                inventory_item=item,
                movement_type=StockMovement.MovementType.OUTBOUND,
                quantity_delta=-per_step,
                reference=f"WO:{step.work_order.wo_number} Step:{step.sequence}",
                performed_by=user,
                created_by=user,
                updated_by=user,
            )


def create_pick_list_from_work_order(wo: WorkOrder, user) -> PickList:
    existing = PickList.objects.filter(work_order=wo).first()
    if existing:
        return existing
    code = f"PL-{wo.wo_number}"
    pl = PickList.objects.create(
        code=code,
        work_order=wo,
        status=PickList.PickStatus.OPEN,
        created_by=user,
        updated_by=user,
    )
    for bom_entry in wo.snapshot.get("bom", []):
        item = InventoryItem.objects.filter(sku=bom_entry.get("inventory_sku")).first()
        if item:
            PickListLine.objects.create(
                pick_list=pl,
                inventory_item=item,
                quantity=Decimal(bom_entry.get("quantity", "0")),
                created_by=user,
                updated_by=user,
            )
    return pl
