from django.shortcuts import render

from core.models import WorkOrder


def manufacturer_panel(request):
    """Shop floor: active work orders from the unified core model."""
    work_orders = WorkOrder.objects.select_related("customer_order", "source_quote").order_by(
        "-priority",
        "delivery_deadline",
    )[:50]
    return render(
        request,
        "manufacturer/manufacturer_panel.html",
        {"work_orders": work_orders},
    )