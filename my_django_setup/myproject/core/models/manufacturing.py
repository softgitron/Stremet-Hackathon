from django.conf import settings
from django.db import models

from .base import BaseEntity


class ManufacturingPlan(BaseEntity):
    """Ordered steps, BOM linkage, estimates for a part or quote."""

    name = models.CharField(max_length=255)
    part = models.ForeignKey(
        "core.Part",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="manufacturing_plans",
    )
    notes = models.TextField(blank=True)
    estimated_total_time_minutes = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
    )
    estimated_total_cost = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        default=0,
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class ManufacturingStep(BaseEntity):
    """Atomic manufacturing step in a plan."""

    class StepStatus(models.TextChoices):
        DRAFT = "draft", "Draft"
        READY = "ready", "Ready"
        ARCHIVED = "archived", "Archived"

    plan = models.ForeignKey(
        ManufacturingPlan,
        on_delete=models.CASCADE,
        related_name="steps",
    )
    sequence = models.PositiveIntegerField(default=1)
    machine_type = models.CharField(max_length=128)
    title = models.CharField(max_length=255, blank=True)
    processing_time_minutes = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
    )
    setup_time_minutes = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
    )
    status = models.CharField(
        max_length=32,
        choices=StepStatus.choices,
        default=StepStatus.DRAFT,
    )
    quality_requirements = models.TextField(blank=True)
    machine_parameters = models.JSONField(default=dict, blank=True)
    template_block = models.ForeignKey(
        "core.DesignBlockTemplate",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="steps_using_template",
    )

    class Meta:
        ordering = ["plan", "sequence"]
        unique_together = [["plan", "sequence"]]

    def __str__(self):
        return f"{self.plan_id} step {self.sequence}"


class StepInputMaterial(BaseEntity):
    """Input material reference for a step (BOM line consumption)."""

    step = models.ForeignKey(
        ManufacturingStep,
        on_delete=models.CASCADE,
        related_name="input_materials",
    )
    inventory_item = models.ForeignKey(
        "core.InventoryItem",
        on_delete=models.PROTECT,
        related_name="step_inputs",
    )
    quantity = models.DecimalField(max_digits=14, decimal_places=4)
    unit = models.CharField(max_length=32, default="pcs")


class StepOutputPart(BaseEntity):
    """Output part reference for a step."""

    step = models.ForeignKey(
        ManufacturingStep,
        on_delete=models.CASCADE,
        related_name="output_parts",
    )
    part = models.ForeignKey(
        "core.Part",
        on_delete=models.CASCADE,
        related_name="step_outputs",
    )
    quantity = models.PositiveIntegerField(default=1)


class StepArtifact(BaseEntity):
    """Artifacts attached to a manufacturing step."""

    class ArtifactKind(models.TextChoices):
        MODEL_3D = "model_3d", "3D Model"
        MACHINE_SCRIPT = "machine_script", "Machine Script"
        SOP = "sop", "SOP"
        OTHER = "other", "Other"

    step = models.ForeignKey(
        ManufacturingStep,
        on_delete=models.CASCADE,
        related_name="artifacts",
    )
    kind = models.CharField(max_length=32, choices=ArtifactKind.choices)
    file = models.FileField(upload_to="steps/artifacts/%Y/%m/", blank=True)
    text_content = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="step_artifacts_uploaded",
    )

    class Meta:
        ordering = ["kind", "created_at"]


class DesignBlockTemplate(BaseEntity):
    """Reusable parameterized design block (e.g. laser cutting step)."""

    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    default_machine_type = models.CharField(max_length=128, blank=True)
    default_parameters = models.JSONField(default=dict, blank=True)
    version_tag = models.CharField(max_length=64, default="1.0.0")

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.version_tag})"


class BOMNode(BaseEntity):
    """Hierarchical BOM linked to inventory and optionally to a plan."""

    manufacturing_plan = models.ForeignKey(
        ManufacturingPlan,
        on_delete=models.CASCADE,
        related_name="bom_nodes",
    )
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="children",
    )
    inventory_item = models.ForeignKey(
        "core.InventoryItem",
        on_delete=models.PROTECT,
        related_name="bom_usages",
    )
    quantity = models.DecimalField(max_digits=14, decimal_places=4)
    unit = models.CharField(max_length=32, default="pcs")
    sequence = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["manufacturing_plan", "sequence"]
