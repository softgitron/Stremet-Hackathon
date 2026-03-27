from django.conf import settings
from django.db import models

from .base import BaseEntity


class WorkOrder(BaseEntity):
    """Production work order with immutable snapshot from approved quote."""

    class WOPriority(models.IntegerChoices):
        LOW = 1, "Low"
        NORMAL = 3, "Normal"
        HIGH = 5, "High"

    wo_number = models.CharField(max_length=64, unique=True)
    customer_order = models.ForeignKey(
        "core.CustomerOrder",
        on_delete=models.CASCADE,
        related_name="work_orders",
    )
    source_quote = models.ForeignKey(
        "core.Quote",
        on_delete=models.PROTECT,
        related_name="work_orders",
    )
    snapshot = models.JSONField(
        help_text="Immutable snapshot: manufacturing plan, BOM, cost at creation.",
    )
    delivery_deadline = models.DateField(null=True, blank=True)
    priority = models.PositiveSmallIntegerField(
        default=WOPriority.NORMAL,
        choices=WOPriority.choices,
    )
    completion_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.wo_number


class WorkOrderStep(BaseEntity):
    """Execution tracking for a work order step (from snapshot)."""

    class ExecutionStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        READY = "ready", "Ready"
        IN_PROGRESS = "in_progress", "In Progress"
        COMPLETED = "completed", "Completed"
        BLOCKED = "blocked", "Blocked"

    work_order = models.ForeignKey(
        WorkOrder,
        on_delete=models.CASCADE,
        related_name="steps",
    )
    sequence = models.PositiveIntegerField()
    snapshot_step_key = models.CharField(
        max_length=64,
        blank=True,
        help_text="Key/id from immutable snapshot step if present.",
    )
    title = models.CharField(max_length=255, blank=True)
    machine_type = models.CharField(max_length=128, blank=True)
    status = models.CharField(
        max_length=32,
        choices=ExecutionStatus.choices,
        default=ExecutionStatus.PENDING,
        db_index=True,
    )
    machine = models.ForeignKey(
        "core.Machine",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="work_order_steps",
    )
    planned_start = models.DateTimeField(null=True, blank=True)
    planned_end = models.DateTimeField(null=True, blank=True)
    actual_start = models.DateTimeField(null=True, blank=True)
    actual_end = models.DateTimeField(null=True, blank=True)
    issue_log = models.TextField(blank=True)
    qc_result_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["work_order", "sequence"]
        unique_together = [["work_order", "sequence"]]


class ScheduledStep(BaseEntity):
    """Scheduling assignment: step to machine with optional manual override flag."""

    work_order_step = models.ForeignKey(
        WorkOrderStep,
        on_delete=models.CASCADE,
        related_name="schedules",
    )
    machine = models.ForeignKey(
        "core.Machine",
        on_delete=models.CASCADE,
        related_name="scheduled_steps",
    )
    planned_start = models.DateTimeField()
    planned_end = models.DateTimeField()
    manual_override = models.BooleanField(default=False)

    class Meta:
        ordering = ["planned_start"]


class ResourceEstimate(BaseEntity):
    """Automatic resource estimate for planning (machines, labor, materials)."""

    manufacturing_plan = models.ForeignKey(
        "core.ManufacturingPlan",
        on_delete=models.CASCADE,
        related_name="resource_estimates",
    )
    required_machine_hours = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    required_labor_hours = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    material_requirements = models.JSONField(default=list)
    computed_at = models.DateTimeField(auto_now_add=True)
