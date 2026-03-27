from django.conf import settings
from django.db import models

from .base import BaseEntity


class QualityReport(BaseEntity):
    """QC result per step with traceability."""

    class Result(models.TextChoices):
        PASS = "pass", "Pass"
        FAIL = "fail", "Fail"
        PENDING = "pending", "Pending"

    work_order_step = models.ForeignKey(
        "core.WorkOrderStep",
        on_delete=models.CASCADE,
        related_name="quality_reports",
    )
    machine = models.ForeignKey(
        "core.Machine",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="quality_reports",
    )
    operator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="quality_reports_operated",
    )
    material_batch = models.CharField(max_length=128, blank=True)
    result = models.CharField(
        max_length=16,
        choices=Result.choices,
        default=Result.PENDING,
    )
    inspection_notes = models.TextField(blank=True)
    root_cause_hint = models.TextField(blank=True)
    attachments = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["-created_at"]
