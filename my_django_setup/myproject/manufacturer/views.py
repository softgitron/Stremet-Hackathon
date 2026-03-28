from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, render

from core.models import Machine, QualityReport, WorkOrder, WorkOrderStep


def manufacturer_panel(request):
    work_orders = (
        WorkOrder.objects.select_related("customer_order", "source_quote")
        .annotate(
            total_steps=Count("steps"),
            completed_steps=Count("steps", filter=Q(steps__status=WorkOrderStep.ExecutionStatus.COMPLETED)),
            blocked_steps=Count("steps", filter=Q(steps__status=WorkOrderStep.ExecutionStatus.BLOCKED)),
        )
        .order_by("-priority", "delivery_deadline")[:50]
    )
    machines = Machine.objects.all().order_by("identifier")
    ctx = {
        "work_orders": work_orders,
        "machines": machines,
        "total_wo": WorkOrder.objects.count(),
        "blocked_count": WorkOrderStep.objects.filter(status=WorkOrderStep.ExecutionStatus.BLOCKED).count(),
        "in_progress_count": WorkOrderStep.objects.filter(status=WorkOrderStep.ExecutionStatus.IN_PROGRESS).count(),
    }
    return render(request, "manufacturer/manufacturer_panel.html", ctx)


def work_order_detail(request, wo_id):
    wo = get_object_or_404(
        WorkOrder.objects.select_related("customer_order", "source_quote"),
        pk=wo_id,
    )
    steps = wo.steps.select_related("machine").order_by("sequence")
    qc_reports = QualityReport.objects.filter(
        work_order_step__work_order=wo
    ).select_related("work_order_step", "operator").order_by("-created_at")
    return render(
        request,
        "manufacturer/work_order_detail.html",
        {"wo": wo, "steps": steps, "qc_reports": qc_reports},
    )
