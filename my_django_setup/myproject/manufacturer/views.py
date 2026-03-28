from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from core.models import Machine, QualityReport, WorkOrder, WorkOrderStep
from core.services import auto_schedule_work_order, create_pick_list_from_work_order, log_audit, reserve_materials_for_step


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

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "start_step":
            step_id = request.POST.get("step_id")
            step = get_object_or_404(WorkOrderStep, pk=step_id, work_order=wo)
            if step.status in (WorkOrderStep.ExecutionStatus.PENDING, WorkOrderStep.ExecutionStatus.READY):
                step.status = WorkOrderStep.ExecutionStatus.IN_PROGRESS
                step.actual_start = timezone.now()
                step.updated_by = request.user
                step.save()
                reserve_materials_for_step(step, request.user)
                log_audit(user=request.user, action="step_started", entity_type="WorkOrderStep", entity_id=str(step.id), after={"status": step.status})
                messages.success(request, f"Step {step.sequence} started.")
            else:
                messages.error(request, "Step cannot be started from its current status.")

        elif action == "complete_step":
            step_id = request.POST.get("step_id")
            step = get_object_or_404(WorkOrderStep, pk=step_id, work_order=wo)
            if step.status == WorkOrderStep.ExecutionStatus.IN_PROGRESS:
                step.status = WorkOrderStep.ExecutionStatus.COMPLETED
                step.actual_end = timezone.now()
                step.updated_by = request.user
                step.save()
                all_steps = list(wo.steps.all())
                done = sum(1 for s in all_steps if s.status == WorkOrderStep.ExecutionStatus.COMPLETED)
                wo.completion_percent = (Decimal(done) / Decimal(len(all_steps)) * 100).quantize(Decimal("0.01"))
                wo.save(update_fields=["completion_percent", "updated_at"])
                log_audit(user=request.user, action="step_completed", entity_type="WorkOrderStep", entity_id=str(step.id), after={"status": step.status})
                messages.success(request, f"Step {step.sequence} completed.")
            else:
                messages.error(request, "Only in-progress steps can be completed.")

        elif action == "block_step":
            step_id = request.POST.get("step_id")
            issue = request.POST.get("issue", "")
            step = get_object_or_404(WorkOrderStep, pk=step_id, work_order=wo)
            step.status = WorkOrderStep.ExecutionStatus.BLOCKED
            step.issue_log = issue
            step.updated_by = request.user
            step.save()
            log_audit(user=request.user, action="step_blocked", entity_type="WorkOrderStep", entity_id=str(step.id), after={"status": step.status, "issue": issue})
            messages.success(request, f"Step {step.sequence} blocked.")

        elif action == "add_qc":
            step_id = request.POST.get("step_id")
            result = request.POST.get("result", "pending")
            notes = request.POST.get("inspection_notes", "")
            batch = request.POST.get("material_batch", "")
            step = get_object_or_404(WorkOrderStep, pk=step_id, work_order=wo)
            QualityReport.objects.create(
                work_order_step=step, result=result,
                inspection_notes=notes, material_batch=batch,
                operator=request.user, machine=step.machine,
                created_by=request.user, updated_by=request.user,
            )
            messages.success(request, "Quality report added.")

        elif action == "auto_schedule":
            results = auto_schedule_work_order(wo, request.user)
            messages.success(request, f"Scheduled {len(results)} step(s).")

        elif action == "generate_picklist":
            pl = create_pick_list_from_work_order(wo, request.user)
            messages.success(request, f"Pick list {pl.code} generated.")

        elif action == "set_machine_state":
            machine_id = request.POST.get("machine_id")
            new_state = request.POST.get("state")
            machine = get_object_or_404(Machine, pk=machine_id)
            old = machine.state
            machine.state = new_state
            machine.save()
            log_audit(user=request.user, action="machine_state_change", entity_type="Machine", entity_id=str(machine.id), before={"state": old}, after={"state": new_state})
            messages.success(request, f"Machine {machine.identifier} set to {new_state}.")

        return redirect("manufacturer_wo_detail", wo_id=wo.id)

    machines = Machine.objects.all().order_by("identifier")
    ctx = {"wo": wo, "steps": steps, "qc_reports": qc_reports, "machines": machines}
    return render(request, "manufacturer/work_order_detail.html", ctx)
