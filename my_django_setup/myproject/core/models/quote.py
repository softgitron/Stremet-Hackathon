from django.conf import settings
from django.db import models

from .base import BaseEntity


class Quote(BaseEntity):
    """Quotation with lifecycle, optional preliminary manufacturing plan, recalc flag."""

    class QuoteState(models.TextChoices):
        DRAFT = "draft", "Draft"
        IN_REVIEW = "in_review", "In Review"
        CUSTOMER_REVIEW = "customer_review", "Customer Review"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        EXPIRED = "expired", "Expired"

    quote_number = models.CharField(max_length=64, unique=True)
    customer = models.ForeignKey(
        "core.Customer",
        on_delete=models.CASCADE,
        related_name="quotes",
    )
    state = models.CharField(
        max_length=32,
        choices=QuoteState.choices,
        default=QuoteState.DRAFT,
        db_index=True,
    )
    title = models.CharField(max_length=255, blank=True)
    valid_until = models.DateField(null=True, blank=True)
    preliminary_manufacturing_plan = models.ForeignKey(
        "core.ManufacturingPlan",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="quotes_using_plan",
    )
    needs_recalculation = models.BooleanField(default=False)
    total_price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )
    currency = models.CharField(max_length=8, default="EUR")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.quote_number} ({self.get_state_display()})"


class QuoteLine(BaseEntity):
    """Line item on a quote for pricing and BOM linkage."""

    quote = models.ForeignKey(
        Quote,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    description = models.CharField(max_length=512)
    quantity = models.DecimalField(max_digits=14, decimal_places=4, default=1)
    unit_price = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    part = models.ForeignKey(
        "core.Part",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="quote_lines",
    )

    class Meta:
        ordering = ["created_at"]

    @property
    def line_total(self):
        return self.quantity * self.unit_price


class QuoteStateTransition(BaseEntity):
    """Audit log for quote workflow transitions."""

    quote = models.ForeignKey(
        Quote,
        on_delete=models.CASCADE,
        related_name="state_transitions",
    )
    from_state = models.CharField(max_length=32, blank=True)
    to_state = models.CharField(max_length=32)
    transitioned_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="quote_transitions",
    )
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["transitioned_at"]

    def __str__(self):
        return f"{self.quote_id}: {self.from_state} → {self.to_state}"


class QuoteDiscussionThread(BaseEntity):
    """Thread container for quote collaboration (ticketing-style)."""

    quote = models.ForeignKey(
        Quote,
        on_delete=models.CASCADE,
        related_name="threads",
    )
    subject = models.CharField(max_length=255, blank=True)
    is_resolved = models.BooleanField(default=False)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return self.subject or f"Thread {self.pk}"


class CommentAuthorRole(models.TextChoices):
    CUSTOMER = "customer", "Customer"
    SALES = "sales", "Sales"
    DESIGNER = "designer", "Designer"
    INTERNAL = "internal", "Internal"


class QuoteComment(BaseEntity):
    """Threaded comment on a quote discussion thread."""

    thread = models.ForeignKey(
        QuoteDiscussionThread,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="replies",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="quote_comments",
    )
    author_role = models.CharField(
        max_length=32,
        choices=CommentAuthorRole.choices,
        default=CommentAuthorRole.INTERNAL,
    )
    body = models.TextField()

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Comment {self.pk}"


class QuoteAttachment(BaseEntity):
    """File attachment on a quote (CAD, PDF, images)."""

    quote = models.ForeignKey(
        Quote,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    file = models.FileField(upload_to="quotes/attachments/%Y/%m/")
    original_name = models.CharField(max_length=512, blank=True)
    content_type = models.CharField(max_length=128, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="quote_attachments_uploaded",
    )

    class Meta:
        ordering = ["-created_at"]


class QuoteVersion(BaseEntity):
    """Immutable snapshot for quote versioning and diff."""

    quote = models.ForeignKey(
        Quote,
        on_delete=models.CASCADE,
        related_name="versions",
    )
    version_number = models.PositiveIntegerField()
    snapshot = models.JSONField(help_text="Full structured snapshot for compare/diff.")

    class Meta:
        ordering = ["-version_number"]
        unique_together = [["quote", "version_number"]]

    def __str__(self):
        return f"{self.quote.quote_number} v{self.version_number}"


class DesignSupportRequest(BaseEntity):
    """Sales-initiated design support; designers accept/reject/clarify."""

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        NORMAL = "normal", "Normal"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"

    class DSStatus(models.TextChoices):
        OPEN = "open", "Open"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"
        CLARIFICATION = "clarification", "Clarification Requested"
        CLOSED = "closed", "Closed"

    quote = models.ForeignKey(
        Quote,
        on_delete=models.CASCADE,
        related_name="design_requests",
    )
    description = models.TextField()
    priority = models.CharField(
        max_length=16,
        choices=Priority.choices,
        default=Priority.NORMAL,
    )
    status = models.CharField(
        max_length=32,
        choices=DSStatus.choices,
        default=DSStatus.OPEN,
    )
    assigned_designer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="design_requests_assigned",
    )
    preliminary_plan = models.ForeignKey(
        "core.ManufacturingPlan",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="design_requests",
    )
    designer_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]


class DesignSupportAttachment(BaseEntity):
    """Attachment on a design support request."""

    design_request = models.ForeignKey(
        DesignSupportRequest,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    file = models.FileField(upload_to="design_requests/%Y/%m/")
    original_name = models.CharField(max_length=512, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="design_support_attachments",
    )


class QuoteCostBreakdown(BaseEntity):
    """Traceable, reproducible cost calculation for a quote."""

    quote = models.OneToOneField(
        Quote,
        on_delete=models.CASCADE,
        related_name="cost_breakdown",
    )
    material_cost = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    machine_time_cost = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    labor_cost = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    overhead_cost = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    total = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    inputs = models.JSONField(
        default=dict,
        help_text="Inputs and intermediate values for audit/reproducibility.",
    )
    computed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Quote cost breakdown"
        verbose_name_plural = "Quote cost breakdowns"
