import uuid
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from core.models import (
    AuditLogEntry,
    BOMNode,
    Customer,
    CustomerOrder,
    DesignBlockTemplate,
    DesignSupportRequest,
    InAppNotification,
    InventoryItem,
    Machine,
    MachineMaintenanceWindow,
    ManufacturingPlan,
    ManufacturingStep,
    Part,
    PickList,
    QualityReport,
    Quote,
    QuoteAttachment,
    QuoteComment,
    QuoteDiscussionThread,
    QuoteLine,
    StepArtifact,
    UserProfile,
    WarehouseLocation,
    WorkOrder,
    WorkOrderStep,
)
from core.models.base import UserRole
from core.services import (
    auto_schedule_work_order,
    compute_quote_cost,
    create_pick_list_from_work_order,
    save_quote_version,
    transition_quote,
)


def dashboard(request):
    return render(request, "home/index.html")


# ---------------------------------------------------------------------------
# Sales portal
# ---------------------------------------------------------------------------
def portal_sales(request):
    quotes = Quote.objects.all()
    ctx = {
        "quote_total": quotes.count(),
        "quote_by_state": list(
            quotes.values("state").annotate(n=Count("id")).order_by("state")
        ),
        "quotes_recent": quotes.select_related("customer").order_by("-created_at")[:15],
        "quotes_needing_recalc": quotes.filter(needs_recalculation=True).count(),
        "open_design_requests": DesignSupportRequest.objects.filter(
            status__in=[DesignSupportRequest.DSStatus.OPEN, DesignSupportRequest.DSStatus.CLARIFICATION]
        ).count(),
        "design_requests": DesignSupportRequest.objects.select_related("quote", "assigned_designer").order_by("-created_at")[:10],
        "total_revenue": quotes.filter(state=Quote.QuoteState.APPROVED).aggregate(total=Sum("total_price"))["total"] or Decimal("0"),
        "customers": Customer.objects.all(),
        "plans": ManufacturingPlan.objects.all(),
    }
    return render(request, "home/portal_sales.html", ctx)


@login_required
def sales_create_quote(request):
    if request.method == "POST":
        customer_id = request.POST.get("customer")
        title = request.POST.get("title", "").strip()
        plan_id = request.POST.get("preliminary_manufacturing_plan") or None
        customer = get_object_or_404(Customer, pk=customer_id)
        q_num = f"Q-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        plan = ManufacturingPlan.objects.filter(pk=plan_id).first() if plan_id else None
        quote = Quote.objects.create(
            quote_number=q_num, customer=customer, title=title,
            preliminary_manufacturing_plan=plan,
            created_by=request.user, updated_by=request.user,
        )
        desc = request.POST.get("line_description", "").strip()
        qty = request.POST.get("line_quantity", "")
        price = request.POST.get("line_unit_price", "")
        if desc and qty and price:
            QuoteLine.objects.create(
                quote=quote, description=desc,
                quantity=Decimal(qty), unit_price=Decimal(price),
                created_by=request.user, updated_by=request.user,
            )
        save_quote_version(quote, request.user)
        messages.success(request, f"Quote {q_num} created.")
        return redirect("sales_quote_detail", quote_id=quote.id)
    ctx = {
        "customers": Customer.objects.order_by("company_name"),
        "plans": ManufacturingPlan.objects.order_by("name"),
    }
    return render(request, "home/sales_create_quote.html", ctx)


@login_required
def sales_quote_detail(request, quote_id):
    quote = get_object_or_404(Quote.objects.select_related("customer", "preliminary_manufacturing_plan"), pk=quote_id)
    lines = quote.lines.order_by("created_at")
    transitions = quote.state_transitions.select_related("user").order_by("transitioned_at")
    threads = quote.threads.order_by("created_at")
    attachments = quote.attachments.order_by("-created_at")

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "add_line":
            desc = request.POST.get("description", "").strip()
            qty = request.POST.get("quantity", "1")
            price = request.POST.get("unit_price", "0")
            if desc:
                QuoteLine.objects.create(
                    quote=quote, description=desc,
                    quantity=Decimal(qty), unit_price=Decimal(price),
                    created_by=request.user, updated_by=request.user,
                )
                quote.needs_recalculation = True
                quote.save(update_fields=["needs_recalculation", "updated_at"])
                messages.success(request, "Line added.")

        elif action == "transition":
            to_state = request.POST.get("to_state")
            note = request.POST.get("note", "")
            try:
                transition_quote(quote, to_state, request.user, note=note)
                messages.success(request, f"Quote moved to {quote.get_state_display()}.")
            except ValueError as e:
                messages.error(request, str(e))

        elif action == "recalculate":
            compute_quote_cost(quote, request.user)
            messages.success(request, "Cost recalculated.")

        elif action == "add_comment":
            thread_id = request.POST.get("thread_id")
            body = request.POST.get("body", "").strip()
            role = request.POST.get("author_role", "internal")
            if body:
                thread = quote.threads.filter(pk=thread_id).first()
                if not thread:
                    thread = QuoteDiscussionThread.objects.create(
                        quote=quote, subject="General", created_by=request.user, updated_by=request.user,
                    )
                QuoteComment.objects.create(
                    thread=thread, body=body, author=request.user, author_role=role,
                    created_by=request.user, updated_by=request.user,
                )
                messages.success(request, "Comment added.")

        elif action == "new_thread":
            subj = request.POST.get("subject", "").strip()
            if subj:
                QuoteDiscussionThread.objects.create(
                    quote=quote, subject=subj, created_by=request.user, updated_by=request.user,
                )
                messages.success(request, f"Thread '{subj}' created.")

        elif action == "upload_attachment":
            f = request.FILES.get("file")
            if f:
                QuoteAttachment.objects.create(
                    quote=quote, file=f, original_name=f.name,
                    content_type=f.content_type or "",
                    uploaded_by=request.user, created_by=request.user, updated_by=request.user,
                )
                messages.success(request, "File attached.")

        elif action == "design_support":
            desc = request.POST.get("ds_description", "").strip()
            pri = request.POST.get("ds_priority", "normal")
            if desc:
                DesignSupportRequest.objects.create(
                    quote=quote, description=desc, priority=pri,
                    created_by=request.user, updated_by=request.user,
                )
                messages.success(request, "Design support request created.")

        return redirect("sales_quote_detail", quote_id=quote.id)

    from core.services import ALLOWED_TRANSITIONS
    allowed = ALLOWED_TRANSITIONS.get(quote.state, set())
    thread_comments = {}
    for t in threads:
        thread_comments[t.id] = t.comments.select_related("author").order_by("created_at")

    ctx = {
        "quote": quote, "lines": lines, "transitions": transitions,
        "threads": threads, "thread_comments": thread_comments,
        "attachments": attachments,
        "allowed_transitions": allowed,
    }
    return render(request, "home/sales_quote_detail.html", ctx)


@login_required
def sales_create_design_request(request):
    if request.method == "POST":
        quote_id = request.POST.get("quote")
        desc = request.POST.get("description", "").strip()
        pri = request.POST.get("priority", "normal")
        quote = get_object_or_404(Quote, pk=quote_id)
        DesignSupportRequest.objects.create(
            quote=quote, description=desc, priority=pri,
            created_by=request.user, updated_by=request.user,
        )
        messages.success(request, "Design support request created.")
        return redirect("portal_sales")
    return redirect("portal_sales")


# ---------------------------------------------------------------------------
# Design portal
# ---------------------------------------------------------------------------
def portal_design(request):
    ctx = {
        "design_open": DesignSupportRequest.objects.filter(
            status__in=[DesignSupportRequest.DSStatus.OPEN, DesignSupportRequest.DSStatus.CLARIFICATION]
        ).count(),
        "design_total": DesignSupportRequest.objects.count(),
        "design_requests": DesignSupportRequest.objects.select_related("quote", "assigned_designer").order_by("-created_at")[:20],
        "plans": ManufacturingPlan.objects.select_related("part").order_by("-created_at")[:15],
        "plans_total": ManufacturingPlan.objects.count(),
        "blocks_total": DesignBlockTemplate.objects.count(),
        "blocks": DesignBlockTemplate.objects.order_by("-created_at")[:10],
    }
    return render(request, "home/portal_design.html", ctx)


@login_required
def design_create_plan(request):
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        part_id = request.POST.get("part") or None
        part = Part.objects.filter(pk=part_id).first() if part_id else None
        plan = ManufacturingPlan.objects.create(
            name=name, part=part, created_by=request.user, updated_by=request.user,
        )
        messages.success(request, f"Plan '{name}' created.")
        return redirect("design_plan_detail", plan_id=plan.id)
    ctx = {"parts": Part.objects.order_by("name")}
    return render(request, "home/design_create_plan.html", ctx)


@login_required
def design_plan_detail(request, plan_id):
    plan = get_object_or_404(ManufacturingPlan.objects.select_related("part"), pk=plan_id)
    steps = plan.steps.order_by("sequence")
    bom = plan.bom_nodes.select_related("inventory_item").order_by("sequence")

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "add_step":
            seq = request.POST.get("sequence", "1")
            mtype = request.POST.get("machine_type", "").strip()
            title = request.POST.get("title", "").strip()
            proc = request.POST.get("processing_time_minutes", "0")
            setup = request.POST.get("setup_time_minutes", "0")
            if mtype:
                ManufacturingStep.objects.create(
                    plan=plan, sequence=int(seq), machine_type=mtype, title=title,
                    processing_time_minutes=Decimal(proc), setup_time_minutes=Decimal(setup),
                    created_by=request.user, updated_by=request.user,
                )
                messages.success(request, f"Step '{title or mtype}' added.")

        elif action == "add_bom":
            inv_id = request.POST.get("inventory_item")
            qty = request.POST.get("quantity", "1")
            unit = request.POST.get("unit", "pcs")
            if inv_id:
                item = get_object_or_404(InventoryItem, pk=inv_id)
                BOMNode.objects.create(
                    manufacturing_plan=plan, inventory_item=item,
                    quantity=Decimal(qty), unit=unit,
                    sequence=bom.count() + 1,
                    created_by=request.user, updated_by=request.user,
                )
                messages.success(request, f"BOM entry for {item.sku} added.")

        return redirect("design_plan_detail", plan_id=plan.id)

    ctx = {
        "plan": plan, "steps": steps, "bom": bom,
        "inventory_items": InventoryItem.objects.order_by("sku"),
    }
    return render(request, "home/design_plan_detail.html", ctx)


@login_required
def design_create_block(request):
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        desc = request.POST.get("description", "").strip()
        mtype = request.POST.get("default_machine_type", "").strip()
        tag = request.POST.get("version_tag", "1.0.0").strip()
        if name:
            DesignBlockTemplate.objects.create(
                name=name, description=desc, default_machine_type=mtype, version_tag=tag,
                created_by=request.user, updated_by=request.user,
            )
            messages.success(request, f"Design block '{name}' created.")
        return redirect("portal_design")
    return render(request, "home/design_create_block.html")


# ---------------------------------------------------------------------------
# Warehouse portal
# ---------------------------------------------------------------------------
def portal_warehouse(request):
    inventory_qs = InventoryItem.objects.select_related("location")
    ctx = {
        "inventory_items": inventory_qs.count(),
        "inventory_list": inventory_qs.order_by("sku")[:30],
        "pick_open": PickList.objects.exclude(status=PickList.PickStatus.COMPLETED).count(),
        "pick_lists": PickList.objects.select_related("work_order").order_by("-created_at")[:15],
        "locations": WarehouseLocation.objects.annotate(item_count=Count("inventory_items")).order_by("code")[:20],
        "low_stock": inventory_qs.filter(quantity__lte=10).order_by("quantity")[:10],
    }
    return render(request, "home/portal_warehouse.html", ctx)


@login_required
def warehouse_create_location(request):
    if request.method == "POST":
        code = request.POST.get("code", "").strip()
        name = request.POST.get("name", "").strip()
        if code:
            WarehouseLocation.objects.create(
                code=code, name=name, created_by=request.user, updated_by=request.user,
            )
            messages.success(request, f"Location '{code}' created.")
        return redirect("portal_warehouse")
    return render(request, "home/warehouse_create_location.html")


@login_required
def warehouse_create_item(request):
    if request.method == "POST":
        sku = request.POST.get("sku", "").strip()
        name = request.POST.get("name", "").strip()
        loc_id = request.POST.get("location")
        qty = request.POST.get("quantity", "0")
        unit = request.POST.get("unit", "pcs")
        cost = request.POST.get("unit_cost", "0")
        batch = request.POST.get("batch_or_lot", "")
        if sku and loc_id:
            loc = get_object_or_404(WarehouseLocation, pk=loc_id)
            InventoryItem.objects.create(
                sku=sku, name=name, location=loc,
                quantity=Decimal(qty), unit=unit,
                unit_cost=Decimal(cost) if cost else None,
                batch_or_lot=batch,
                created_by=request.user, updated_by=request.user,
            )
            messages.success(request, f"Item '{sku}' created.")
        return redirect("portal_warehouse")
    ctx = {"locations": WarehouseLocation.objects.order_by("code")}
    return render(request, "home/warehouse_create_item.html", ctx)


@login_required
def warehouse_adjust_stock(request, item_id):
    item = get_object_or_404(InventoryItem, pk=item_id)
    if request.method == "POST":
        delta = Decimal(request.POST.get("quantity_delta", "0"))
        mtype = request.POST.get("movement_type", "adjust")
        ref = request.POST.get("reference", "")
        from core.models import StockMovement
        item.quantity += delta
        item.save()
        StockMovement.objects.create(
            inventory_item=item, movement_type=mtype, quantity_delta=delta,
            reference=ref, performed_by=request.user,
            created_by=request.user, updated_by=request.user,
        )
        messages.success(request, f"Stock adjusted by {delta}.")
        return redirect("portal_warehouse")
    return render(request, "home/warehouse_adjust_stock.html", {"item": item})


# ---------------------------------------------------------------------------
# Ops Admin portal
# ---------------------------------------------------------------------------
def portal_admin(request):
    now = timezone.now()
    wo_qs = WorkOrder.objects.all()
    machine_qs = Machine.objects.all()
    ctx = {
        "orders": CustomerOrder.objects.count(),
        "work_orders": wo_qs.count(),
        "quotes": Quote.objects.count(),
        "machines": machine_qs.count(),
        "inventory_items": InventoryItem.objects.count(),
        "users": UserProfile.objects.count(),
        "avg_completion": wo_qs.aggregate(avg=Avg("completion_percent"))["avg"] or Decimal("0"),
        "machines_available": machine_qs.filter(state=Machine.MachineState.AVAILABLE).count(),
        "machines_busy": machine_qs.filter(state=Machine.MachineState.BUSY).count(),
        "machines_maintenance": machine_qs.filter(state=Machine.MachineState.MAINTENANCE).count(),
        "machines_offline": machine_qs.filter(state=Machine.MachineState.OFFLINE).count(),
        "overdue_orders": CustomerOrder.objects.filter(
            delivery_deadline__lt=now.date(),
            status__in=[CustomerOrder.OrderStatus.OPEN, CustomerOrder.OrderStatus.IN_PROGRESS],
        ).count(),
        "approved_revenue": Quote.objects.filter(state=Quote.QuoteState.APPROVED).aggregate(
            total=Sum("total_price")
        )["total"] or Decimal("0"),
        "recent_audit": AuditLogEntry.objects.order_by("-timestamp")[:15],
        "recent_notifications": InAppNotification.objects.order_by("-created_at")[:10],
        "blocked_steps": WorkOrderStep.objects.filter(status=WorkOrderStep.ExecutionStatus.BLOCKED).count(),
    }
    return render(request, "home/portal_admin.html", ctx)


@login_required
def admin_create_customer(request):
    if request.method == "POST":
        name = request.POST.get("company_name", "").strip()
        email = request.POST.get("email", "").strip()
        phone = request.POST.get("phone", "")
        addr = request.POST.get("billing_address", "")
        if name and email:
            Customer.objects.create(
                company_name=name, email=email, phone=phone, billing_address=addr,
                created_by=request.user, updated_by=request.user,
            )
            messages.success(request, f"Customer '{name}' created.")
        return redirect("portal_admin")
    return render(request, "home/admin_create_customer.html")


@login_required
def admin_create_machine(request):
    if request.method == "POST":
        ident = request.POST.get("identifier", "").strip()
        name = request.POST.get("name", "").strip()
        mtype = request.POST.get("machine_type", "").strip()
        cap = request.POST.get("capacity_hours_per_day", "8")
        if ident and mtype:
            Machine.objects.create(
                identifier=ident, name=name, machine_type=mtype,
                capacity_hours_per_day=Decimal(cap),
                created_by=request.user, updated_by=request.user,
            )
            messages.success(request, f"Machine '{ident}' registered.")
        return redirect("portal_admin")
    return render(request, "home/admin_create_machine.html")


@login_required
def admin_create_part(request):
    if request.method == "POST":
        customer_id = request.POST.get("customer")
        name = request.POST.get("name", "").strip()
        desc = request.POST.get("description", "")
        drawing = request.POST.get("drawing_reference", "")
        qty = request.POST.get("quantity", "1")
        if customer_id and name:
            customer = get_object_or_404(Customer, pk=customer_id)
            Part.objects.create(
                customer=customer, name=name, description=desc,
                drawing_reference=drawing, quantity=int(qty),
                created_by=request.user, updated_by=request.user,
            )
            messages.success(request, f"Part '{name}' created.")
        return redirect("portal_admin")
    ctx = {"customers": Customer.objects.order_by("company_name")}
    return render(request, "home/admin_create_part.html", ctx)
