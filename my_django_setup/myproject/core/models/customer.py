from django.db import models

from .base import BaseEntity


class Customer(BaseEntity):
    """Customer account (company) for quotes and orders."""

    company_name = models.CharField(max_length=255)
    legal_name = models.CharField(max_length=255, blank=True)
    email = models.EmailField(db_index=True)
    phone = models.CharField(max_length=64, blank=True)
    billing_address = models.TextField(blank=True)
    shipping_address = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["company_name"]

    def __str__(self):
        return self.company_name


class Part(BaseEntity):
    """Manufactured part definition linked to a customer order or quote line."""

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="parts",
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    drawing_reference = models.CharField(max_length=128, blank=True)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class CustomerOrder(BaseEntity):
    """Sales order entity (spec: Order). Created from an approved quote or manually."""

    class OrderStatus(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In Progress"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    order_number = models.CharField(max_length=64, unique=True)
    source_quote = models.ForeignKey(
        "core.Quote",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="customer_orders",
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="orders",
    )
    status = models.CharField(
        max_length=32,
        choices=OrderStatus.choices,
        default=OrderStatus.OPEN,
    )
    delivery_deadline = models.DateField(null=True, blank=True)
    priority = models.PositiveSmallIntegerField(default=3)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Order"
        verbose_name_plural = "Orders"

    def __str__(self):
        return self.order_number
