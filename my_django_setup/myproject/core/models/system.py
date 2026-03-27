from django.conf import settings
from django.db import models

from .base import BaseEntity


class StoredFile(BaseEntity):
    """Centralized file metadata with tagging and access control hints."""

    file = models.FileField(upload_to="vault/%Y/%m/")
    original_name = models.CharField(max_length=512, blank=True)
    tags = models.JSONField(default=list, blank=True)
    min_role = models.CharField(
        max_length=32,
        blank=True,
        help_text="Optional minimum role required (matches UserProfile.role).",
    )
    version_label = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ["-created_at"]


class InAppNotification(BaseEntity):
    """Mandatory in-app notifications; email is optional extension."""

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="stremet_notifications",
    )
    title = models.CharField(max_length=255)
    body = models.TextField(blank=True)
    read = models.BooleanField(default=False)
    event_code = models.CharField(max_length=64, blank=True)
    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]


class AuditLogEntry(models.Model):
    """Append-only audit trail for state changes and user actions."""

    id = models.BigAutoField(primary_key=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_entries",
    )
    action = models.CharField(max_length=64)
    entity_type = models.CharField(max_length=64, db_index=True)
    entity_id = models.CharField(max_length=64, db_index=True)
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.action} {self.entity_type}:{self.entity_id}"


class PermissionGrant(BaseEntity):
    """Configurable entity/action grants for admin-tunable RBAC."""

    role = models.CharField(max_length=32, db_index=True)
    entity = models.CharField(max_length=64, db_index=True)
    can_read = models.BooleanField(default=True)
    can_write = models.BooleanField(default=False)
    can_approve = models.BooleanField(default=False)
    can_delete = models.BooleanField(default=False)

    class Meta:
        unique_together = [["role", "entity"]]
        verbose_name = "Permission grant"
        verbose_name_plural = "Permission grants"
