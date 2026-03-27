from django.db import models

from .base import BaseEntity


class Machine(BaseEntity):
    """Machine registry with capabilities and state."""

    class MachineState(models.TextChoices):
        AVAILABLE = "available", "Available"
        BUSY = "busy", "Busy"
        MAINTENANCE = "maintenance", "Maintenance"
        OFFLINE = "offline", "Offline"

    identifier = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=255)
    machine_type = models.CharField(max_length=128)
    capabilities = models.JSONField(default=list, blank=True)
    supported_operations = models.JSONField(default=list, blank=True)
    state = models.CharField(
        max_length=32,
        choices=MachineState.choices,
        default=MachineState.AVAILABLE,
        db_index=True,
    )
    capacity_hours_per_day = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=8,
    )
    scheduled_workload_hours = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
    )
    actual_usage_hours = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
    )
    iot_endpoint = models.CharField(max_length=512, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["identifier"]

    def __str__(self):
        return f"{self.identifier} ({self.name})"


class MachineMaintenanceWindow(BaseEntity):
    """Scheduled maintenance — blocks scheduling for the machine."""

    machine = models.ForeignKey(
        Machine,
        on_delete=models.CASCADE,
        related_name="maintenance_windows",
    )
    title = models.CharField(max_length=255, blank=True)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    blocks_scheduling = models.BooleanField(default=True)
    completed = models.BooleanField(default=False)

    class Meta:
        ordering = ["starts_at"]
