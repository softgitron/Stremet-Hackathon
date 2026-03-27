from decimal import Decimal

from django.db.models import Avg, Count, Q, Sum
from django.shortcuts import render
from django.utils import timezone

from core.models import (
    AuditLogEntry,
    CustomerOrder,
    DesignBlockTemplate,
    DesignSupportRequest,
    InAppNotification,
    InventoryItem,
    Machine,
    ManufacturingPlan,
    PickList,
    Quote,
    UserProfile,
    WarehouseLocation,
    WorkOrder,
    WorkOrderStep,
)


def dashboard(request):
    return render(request, "home/index.html")


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
            status__in=[
                DesignSupportRequest.DSStatus.OPEN,
                DesignSupportRequest.DSStatus.CLARIFICATION,
            ]
        ).count(),
        "design_requests": DesignSupportRequest.objects.select_related(
            "quote", "assigned_designer"
        ).order_by("-created_at")[:10],
        "total_revenue": quotes.filter(state=Quote.QuoteState.APPROVED).aggregate(
            total=Sum("total_price")
        )["total"] or Decimal("0"),
    }
    return render(request, "home/portal_sales.html", ctx)


def portal_design(request):
    ctx = {
        "design_open": DesignSupportRequest.objects.filter(
            status__in=[
                DesignSupportRequest.DSStatus.OPEN,
                DesignSupportRequest.DSStatus.CLARIFICATION,
            ]
        ).count(),
        "design_total": DesignSupportRequest.objects.count(),
        "design_requests": DesignSupportRequest.objects.select_related(
            "quote", "assigned_designer"
        ).order_by("-created_at")[:20],
        "plans": ManufacturingPlan.objects.select_related("part").order_by("-created_at")[:15],
        "plans_total": ManufacturingPlan.objects.count(),
        "blocks_total": DesignBlockTemplate.objects.count(),
        "blocks": DesignBlockTemplate.objects.order_by("-created_at")[:10],
    }
    return render(request, "home/portal_design.html", ctx)


def portal_warehouse(request):
    inventory_qs = InventoryItem.objects.select_related("location")
    ctx = {
        "inventory_items": inventory_qs.count(),
        "inventory_list": inventory_qs.order_by("sku")[:30],
        "pick_open": PickList.objects.exclude(
            status=PickList.PickStatus.COMPLETED
        ).count(),
        "pick_lists": PickList.objects.select_related("work_order").order_by("-created_at")[:15],
        "locations": WarehouseLocation.objects.annotate(
            item_count=Count("inventory_items")
        ).order_by("code")[:20],
        "low_stock": inventory_qs.filter(quantity__lte=10).order_by("quantity")[:10],
    }
    return render(request, "home/portal_warehouse.html", ctx)


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
        "blocked_steps": WorkOrderStep.objects.filter(
            status=WorkOrderStep.ExecutionStatus.BLOCKED
        ).count(),
    }
    return render(request, "home/portal_admin.html", ctx)
