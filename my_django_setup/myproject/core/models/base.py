import uuid

from django.conf import settings
from django.db import models


class BaseEntity(models.Model):
    """UUID primary key, revision, and audit fields for all core entities."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    revision = models.PositiveIntegerField(default=1, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="%(class)s_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="%(class)s_updated",
    )

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if self.pk is not None:
            self.revision = (self.revision or 0) + 1
        super().save(*args, **kwargs)


class UserRole(models.TextChoices):
    CUSTOMER = "customer", "Customer"
    SALES = "sales", "Sales"
    DESIGNER = "designer", "Designer"
    MANUFACTURER = "manufacturer", "Manufacturer"
    WAREHOUSE = "warehouse", "Warehouse Personnel"
    ADMINISTRATOR = "administrator", "Administrator"


class UserProfile(BaseEntity):
    """Extended user with portal role and customer scoping for data visibility."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="stremet_profile",
    )
    role = models.CharField(
        max_length=32,
        choices=UserRole.choices,
        default=UserRole.CUSTOMER,
    )
    customer = models.ForeignKey(
        "core.Customer",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="portal_users",
        help_text="When role is customer, limits visibility to this customer account.",
    )

    class Meta:
        verbose_name = "User profile"
        verbose_name_plural = "User profiles"

    def __str__(self):
        return f"{self.user.get_username()} ({self.get_role_display()})"
