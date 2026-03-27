from django.conf import settings
from django.db import models

from .base import BaseEntity


class WarehouseLocation(BaseEntity):
    """Bin/shelf/zone with optional capacity constraint."""

    code = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=255, blank=True)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="children",
    )
    max_weight_kg = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    max_volume_m3 = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return self.code


class InventoryItem(BaseEntity):
    """Stock item with quantity, location, status, optional lot."""

    class InventoryStatus(models.TextChoices):
        AVAILABLE = "available", "Available"
        RESERVED = "reserved", "Reserved"
        IN_PRODUCTION = "in_production", "In Production"

    sku = models.CharField(max_length=128, unique=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    quantity = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    unit = models.CharField(max_length=32, default="pcs")
    location = models.ForeignKey(
        WarehouseLocation,
        on_delete=models.PROTECT,
        related_name="inventory_items",
    )
    status = models.CharField(
        max_length=32,
        choices=InventoryStatus.choices,
        default=InventoryStatus.AVAILABLE,
    )
    batch_or_lot = models.CharField(max_length=128, blank=True)
    unit_cost = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["sku"]

    def __str__(self):
        return f"{self.sku} — {self.name}"


class PickList(BaseEntity):
    """Outbound picking list generated from a work order."""

    class PickStatus(models.TextChoices):
        OPEN = "open", "Open"
        PICKING = "picking", "Picking"
        COMPLETED = "completed", "Completed"

    code = models.CharField(max_length=64, unique=True)
    work_order = models.ForeignKey(
        "core.WorkOrder",
        on_delete=models.CASCADE,
        related_name="pick_lists",
    )
    status = models.CharField(
        max_length=32,
        choices=PickStatus.choices,
        default=PickStatus.OPEN,
    )

    class Meta:
        ordering = ["-created_at"]


class PickListLine(BaseEntity):
    pick_list = models.ForeignKey(
        PickList,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    inventory_item = models.ForeignKey(
        InventoryItem,
        on_delete=models.PROTECT,
        related_name="pick_lines",
    )
    quantity = models.DecimalField(max_digits=14, decimal_places=4)
    picked = models.DecimalField(max_digits=14, decimal_places=4, default=0)

    class Meta:
        ordering = ["created_at"]


class StockMovement(BaseEntity):
    """Inbound/outbound stock movement audit."""

    class MovementType(models.TextChoices):
        INBOUND = "inbound", "Inbound"
        OUTBOUND = "outbound", "Outbound"
        ADJUST = "adjust", "Adjustment"

    inventory_item = models.ForeignKey(
        InventoryItem,
        on_delete=models.CASCADE,
        related_name="movements",
    )
    movement_type = models.CharField(max_length=16, choices=MovementType.choices)
    quantity_delta = models.DecimalField(max_digits=14, decimal_places=4)
    reference = models.CharField(max_length=128, blank=True)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="stock_movements",
    )

    class Meta:
        ordering = ["-created_at"]
