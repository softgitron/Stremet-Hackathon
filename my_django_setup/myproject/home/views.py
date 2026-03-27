from django.db.models import Count
from django.shortcuts import render

from core.models import (
    CustomerOrder,
    DesignSupportRequest,
    InventoryItem,
    Machine,
    PickList,
    Quote,
    WorkOrder,
)


def dashboard(request):
    """Landing page with role-based portal entry points."""
    return render(request, "home/index.html")


def portal_sales(request):
    """Sales: quotes, customer interactions, design requests (summary)."""
    quotes = Quote.objects.all()
    ctx = {
        "quote_total": quotes.count(),
        "quote_by_state": list(
            quotes.values("state").annotate(n=Count("id")).order_by("state")
        ),
        "open_design_requests": DesignSupportRequest.objects.filter(
            status__in=[
                DesignSupportRequest.DSStatus.OPEN,
                DesignSupportRequest.DSStatus.CLARIFICATION,
            ]
        ).count(),
    }
    return render(request, "home/portal_sales.html", ctx)


def portal_design(request):
    """Designer: open design requests, manufacturing plans overview."""
    ctx = {
        "design_open": DesignSupportRequest.objects.filter(
            status__in=[
                DesignSupportRequest.DSStatus.OPEN,
                DesignSupportRequest.DSStatus.CLARIFICATION,
            ]
        ).count(),
        "design_total": DesignSupportRequest.objects.count(),
    }
    return render(request, "home/portal_design.html", ctx)


def portal_warehouse(request):
    """Warehouse: picking, inventory, locations (summary)."""
    ctx = {
        "inventory_items": InventoryItem.objects.count(),
        "pick_open": PickList.objects.exclude(
            status=PickList.PickStatus.COMPLETED
        ).count(),
    }
    return render(request, "home/portal_warehouse.html", ctx)


def portal_admin(request):
    """Administrator: cross-functional KPIs (lightweight)."""
    ctx = {
        "orders": CustomerOrder.objects.count(),
        "work_orders": WorkOrder.objects.count(),
        "quotes": Quote.objects.count(),
        "machines": Machine.objects.count(),
        "inventory_items": InventoryItem.objects.count(),
    }
    return render(request, "home/portal_admin.html", ctx)
