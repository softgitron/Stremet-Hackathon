from django.contrib.auth.models import User
from rest_framework import serializers

from . import models


class UserBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "first_name", "last_name")


class UserProfileSerializer(serializers.ModelSerializer):
    user = UserBriefSerializer(read_only=True)

    class Meta:
        model = models.UserProfile
        fields = (
            "id",
            "revision",
            "created_at",
            "updated_at",
            "user",
            "role",
            "customer",
        )
        read_only_fields = ("revision", "created_at", "updated_at")


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Customer
        fields = "__all__"
        read_only_fields = ("id", "revision", "created_at", "updated_at")


class PartSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Part
        fields = "__all__"
        read_only_fields = ("id", "revision", "created_at", "updated_at")


class QuoteLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.QuoteLine
        fields = "__all__"
        read_only_fields = ("id", "revision", "created_at", "updated_at")


class QuoteSerializer(serializers.ModelSerializer):
    lines = QuoteLineSerializer(many=True, read_only=True)

    class Meta:
        model = models.Quote
        fields = (
            "id",
            "revision",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
            "quote_number",
            "customer",
            "state",
            "title",
            "valid_until",
            "preliminary_manufacturing_plan",
            "needs_recalculation",
            "total_price",
            "currency",
            "lines",
        )
        read_only_fields = ("id", "revision", "created_at", "updated_at")


class QuoteWriteSerializer(serializers.ModelSerializer):
    """Create/update quote without nested lines (use separate endpoint or lines CRUD)."""

    class Meta:
        model = models.Quote
        fields = "__all__"
        read_only_fields = ("id", "revision", "created_at", "updated_at")


class QuoteStateTransitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.QuoteStateTransition
        fields = "__all__"
        read_only_fields = ("id", "revision", "created_at", "updated_at")


class QuoteDiscussionThreadSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.QuoteDiscussionThread
        fields = "__all__"
        read_only_fields = ("id", "revision", "created_at", "updated_at")


class QuoteCommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.QuoteComment
        fields = "__all__"
        read_only_fields = ("id", "revision", "created_at", "updated_at")


class QuoteAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.QuoteAttachment
        fields = "__all__"
        read_only_fields = ("id", "revision", "created_at", "updated_at")


class QuoteVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.QuoteVersion
        fields = "__all__"
        read_only_fields = ("id", "revision", "created_at", "updated_at")


class QuoteCostBreakdownSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.QuoteCostBreakdown
        fields = "__all__"
        read_only_fields = ("id", "revision", "created_at", "updated_at", "computed_at")


class DesignSupportRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.DesignSupportRequest
        fields = "__all__"
        read_only_fields = ("id", "revision", "created_at", "updated_at")


class DesignSupportAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.DesignSupportAttachment
        fields = "__all__"
        read_only_fields = ("id", "revision", "created_at", "updated_at")


class ManufacturingPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.ManufacturingPlan
        fields = "__all__"
        read_only_fields = ("id", "revision", "created_at", "updated_at")


class ManufacturingStepSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.ManufacturingStep
        fields = "__all__"
        read_only_fields = ("id", "revision", "created_at", "updated_at")


class StepInputMaterialSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.StepInputMaterial
        fields = "__all__"
        read_only_fields = ("id", "revision", "created_at", "updated_at")


class StepOutputPartSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.StepOutputPart
        fields = "__all__"
        read_only_fields = ("id", "revision", "created_at", "updated_at")


class StepArtifactSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.StepArtifact
        fields = "__all__"
        read_only_fields = ("id", "revision", "created_at", "updated_at")


class DesignBlockTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.DesignBlockTemplate
        fields = "__all__"
        read_only_fields = ("id", "revision", "created_at", "updated_at")


class BOMNodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.BOMNode
        fields = "__all__"
        read_only_fields = ("id", "revision", "created_at", "updated_at")


class MachineSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Machine
        fields = "__all__"
        read_only_fields = ("id", "revision", "created_at", "updated_at")


class MachineMaintenanceWindowSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.MachineMaintenanceWindow
        fields = "__all__"
        read_only_fields = ("id", "revision", "created_at", "updated_at")


class WarehouseLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.WarehouseLocation
        fields = "__all__"
        read_only_fields = ("id", "revision", "created_at", "updated_at")


class InventoryItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.InventoryItem
        fields = "__all__"
        read_only_fields = ("id", "revision", "created_at", "updated_at")


class CustomerOrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.CustomerOrder
        fields = "__all__"
        read_only_fields = ("id", "revision", "created_at", "updated_at")


class WorkOrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.WorkOrder
        fields = "__all__"
        read_only_fields = (
            "id",
            "revision",
            "created_at",
            "updated_at",
            "snapshot",
            "completion_percent",
        )


class WorkOrderStepSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.WorkOrderStep
        fields = "__all__"
        read_only_fields = ("id", "revision", "created_at", "updated_at")


class ScheduledStepSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.ScheduledStep
        fields = "__all__"
        read_only_fields = ("id", "revision", "created_at", "updated_at")


class ResourceEstimateSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.ResourceEstimate
        fields = "__all__"
        read_only_fields = ("id", "revision", "created_at", "updated_at")


class QualityReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.QualityReport
        fields = "__all__"
        read_only_fields = ("id", "revision", "created_at", "updated_at")


class StoredFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.StoredFile
        fields = "__all__"
        read_only_fields = ("id", "revision", "created_at", "updated_at")


class InAppNotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.InAppNotification
        fields = "__all__"
        read_only_fields = ("id", "revision", "created_at", "updated_at")


class AuditLogEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = models.AuditLogEntry
        fields = "__all__"


class PermissionGrantSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.PermissionGrant
        fields = "__all__"
        read_only_fields = ("id", "revision", "created_at", "updated_at")


class PickListSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.PickList
        fields = "__all__"
        read_only_fields = ("id", "revision", "created_at", "updated_at")


class PickListLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.PickListLine
        fields = "__all__"
        read_only_fields = ("id", "revision", "created_at", "updated_at")


class StockMovementSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.StockMovement
        fields = "__all__"
        read_only_fields = ("id", "revision", "created_at", "updated_at")
