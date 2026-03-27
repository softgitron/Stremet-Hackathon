from decimal import Decimal

from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response

from . import models, serializers
from .services import (
    auto_schedule_work_order,
    compute_quote_cost,
    compute_resource_estimate,
    create_pick_list_from_work_order,
    create_work_order_from_quote,
    log_audit,
    reserve_materials_for_step,
    save_quote_version,
    transition_quote,
)


def _profile(request):
    return getattr(request.user, "stremet_profile", None)


class RoleScopedMixin:
    """Filter querysets for customer role: only own customer_id."""

    customer_field = "customer"

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not user.is_authenticated:
            return qs.none()
        if user.is_superuser:
            return qs
        prof = _profile(self.request)
        if prof and prof.role == models.UserRole.CUSTOMER and prof.customer_id:
            return qs.filter(**{self.customer_field: prof.customer_id})
        return qs


class CustomerViewSet(RoleScopedMixin, viewsets.ModelViewSet):
    queryset = models.Customer.objects.all()
    serializer_class = serializers.CustomerSerializer
    customer_field = "id"
    filterset_fields = ("company_name", "email")
    ordering_fields = ("company_name", "created_at", "updated_at")
    search_fields = ("company_name", "email", "legal_name")

    def get_queryset(self):
        qs = models.Customer.objects.all()
        user = self.request.user
        if not user.is_authenticated:
            return qs.none()
        if user.is_superuser:
            return qs
        prof = _profile(self.request)
        if prof and prof.role == models.UserRole.CUSTOMER and prof.customer_id:
            return qs.filter(pk=prof.customer_id)
        return qs


class PartViewSet(RoleScopedMixin, viewsets.ModelViewSet):
    queryset = models.Part.objects.select_related("customer")
    serializer_class = serializers.PartSerializer
    filterset_fields = ("customer",)
    ordering_fields = ("name", "created_at")
    search_fields = ("name", "drawing_reference")


class QuoteViewSet(RoleScopedMixin, viewsets.ModelViewSet):
    queryset = models.Quote.objects.prefetch_related("lines").select_related("customer")
    serializer_class = serializers.QuoteSerializer
    http_method_names = ["get", "post", "put", "patch", "head", "options"]
    filterset_fields = ("state", "customer", "needs_recalculation", "currency")
    ordering_fields = ("created_at", "updated_at", "quote_number", "state", "total_price", "valid_until")
    search_fields = ("quote_number", "title")

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return serializers.QuoteWriteSerializer
        return serializers.QuoteSerializer

    def perform_create(self, serializer):
        serializer.save(
            created_by=self.request.user,
            updated_by=self.request.user,
        )
        quote = serializer.instance
        save_quote_version(quote, self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)
        quote = serializer.instance
        quote.needs_recalculation = True
        quote.save(update_fields=["needs_recalculation", "updated_at"])
        save_quote_version(quote, self.request.user)

    @extend_schema(
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "to_state": {"type": "string"},
                    "note": {"type": "string"},
                },
                "required": ["to_state"],
            }
        }
    )
    @action(detail=True, methods=["post"], url_path="transition")
    def transition(self, request, pk=None):
        quote = self.get_object()
        to_state = request.data.get("to_state")
        note = request.data.get("note", "")
        try:
            transition_quote(quote, to_state, request.user, note=note)
        except ValueError as e:
            raise ValidationError(str(e)) from e
        ser = serializers.QuoteSerializer(quote)
        return Response(ser.data)

    @action(detail=True, methods=["post"], url_path="recalculate")
    def recalculate(self, request, pk=None):
        quote = self.get_object()
        breakdown = compute_quote_cost(quote, request.user)
        return Response(serializers.QuoteCostBreakdownSerializer(breakdown).data)

    @extend_schema(
        parameters=[
            OpenApiParameter("left", int, required=True),
            OpenApiParameter("right", int, required=True),
        ]
    )
    @action(detail=True, methods=["get"], url_path="compare-versions")
    def compare_versions(self, request, pk=None):
        quote = self.get_object()
        left = request.query_params.get("left")
        right = request.query_params.get("right")
        if left is None or right is None:
            raise ValidationError("Query params left and right (version numbers) required.")
        v1 = quote.versions.filter(version_number=int(left)).first()
        v2 = quote.versions.filter(version_number=int(right)).first()
        if not v1 or not v2:
            raise NotFound("Version not found.")
        return Response({"left": v1.snapshot, "right": v2.snapshot})

    @action(detail=True, methods=["post"], url_path="snapshot-version")
    def snapshot_version(self, request, pk=None):
        quote = self.get_object()
        v = save_quote_version(quote, request.user)
        return Response(serializers.QuoteVersionSerializer(v).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="generate-work-order")
    def generate_work_order(self, request, pk=None):
        quote = self.get_object()
        wo = create_work_order_from_quote(quote, request.user)
        if not wo:
            raise ValidationError("Quote must be approved to generate a work order.")
        return Response(serializers.WorkOrderSerializer(wo).data, status=status.HTTP_201_CREATED)


class QuoteLineViewSet(viewsets.ModelViewSet):
    queryset = models.QuoteLine.objects.select_related("quote", "part")
    serializer_class = serializers.QuoteLineSerializer
    filterset_fields = ("quote", "part")
    ordering_fields = ("created_at", "quantity")

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)
        q = serializer.instance.quote
        q.needs_recalculation = True
        q.save(update_fields=["needs_recalculation", "updated_at"])

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)
        q = serializer.instance.quote
        q.needs_recalculation = True
        q.save(update_fields=["needs_recalculation", "updated_at"])


class QuoteStateTransitionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.QuoteStateTransition.objects.select_related("quote", "user")
    serializer_class = serializers.QuoteStateTransitionSerializer
    filterset_fields = ("quote", "to_state", "from_state")
    ordering_fields = ("transitioned_at",)


class QuoteDiscussionThreadViewSet(viewsets.ModelViewSet):
    queryset = models.QuoteDiscussionThread.objects.select_related("quote")
    serializer_class = serializers.QuoteDiscussionThreadSerializer
    filterset_fields = ("quote", "is_resolved")
    ordering_fields = ("created_at",)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)


class QuoteCommentViewSet(viewsets.ModelViewSet):
    queryset = models.QuoteComment.objects.select_related("thread", "author")
    serializer_class = serializers.QuoteCommentSerializer
    filterset_fields = ("thread", "author", "author_role", "parent")
    ordering_fields = ("created_at",)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user, author=self.request.user)


class QuoteAttachmentViewSet(viewsets.ModelViewSet):
    queryset = models.QuoteAttachment.objects.select_related("quote")
    serializer_class = serializers.QuoteAttachmentSerializer
    filterset_fields = ("quote",)
    ordering_fields = ("created_at",)

    def perform_create(self, serializer):
        serializer.save(
            created_by=self.request.user,
            updated_by=self.request.user,
            uploaded_by=self.request.user,
        )


class QuoteVersionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.QuoteVersion.objects.select_related("quote")
    serializer_class = serializers.QuoteVersionSerializer
    filterset_fields = ("quote", "version_number")
    ordering_fields = ("version_number", "created_at")


class QuoteCostBreakdownViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.QuoteCostBreakdown.objects.select_related("quote")
    serializer_class = serializers.QuoteCostBreakdownSerializer
    filterset_fields = ("quote",)


class DesignSupportRequestViewSet(viewsets.ModelViewSet):
    queryset = models.DesignSupportRequest.objects.select_related("quote", "assigned_designer")
    serializer_class = serializers.DesignSupportRequestSerializer
    filterset_fields = ("quote", "status", "priority", "assigned_designer")
    ordering_fields = ("created_at", "priority")

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)


class DesignSupportAttachmentViewSet(viewsets.ModelViewSet):
    queryset = models.DesignSupportAttachment.objects.select_related("design_request")
    serializer_class = serializers.DesignSupportAttachmentSerializer
    filterset_fields = ("design_request",)

    def perform_create(self, serializer):
        serializer.save(
            created_by=self.request.user,
            updated_by=self.request.user,
            uploaded_by=self.request.user,
        )


class ManufacturingPlanViewSet(viewsets.ModelViewSet):
    queryset = models.ManufacturingPlan.objects.select_related("part")
    serializer_class = serializers.ManufacturingPlanSerializer
    filterset_fields = ("part",)
    ordering_fields = ("name", "created_at", "estimated_total_cost")
    search_fields = ("name", "notes")

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)
        inst = serializer.instance
        models.Quote.objects.filter(preliminary_manufacturing_plan=inst).update(needs_recalculation=True)

    @action(detail=True, methods=["post"], url_path="estimate-resources")
    def estimate_resources(self, request, pk=None):
        plan = self.get_object()
        est = compute_resource_estimate(plan, request.user)
        return Response(serializers.ResourceEstimateSerializer(est).data, status=status.HTTP_201_CREATED)


class ManufacturingStepViewSet(viewsets.ModelViewSet):
    queryset = models.ManufacturingStep.objects.select_related("plan")
    serializer_class = serializers.ManufacturingStepSerializer
    filterset_fields = ("plan", "status", "machine_type", "template_block")
    ordering_fields = ("sequence", "created_at")

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)
        plan = serializer.instance.plan
        models.Quote.objects.filter(preliminary_manufacturing_plan=plan).update(needs_recalculation=True)


class StepInputMaterialViewSet(viewsets.ModelViewSet):
    queryset = models.StepInputMaterial.objects.select_related("step", "inventory_item")
    serializer_class = serializers.StepInputMaterialSerializer
    filterset_fields = ("step", "inventory_item")

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)


class StepOutputPartViewSet(viewsets.ModelViewSet):
    queryset = models.StepOutputPart.objects.select_related("step", "part")
    serializer_class = serializers.StepOutputPartSerializer
    filterset_fields = ("step", "part")

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)


class StepArtifactViewSet(viewsets.ModelViewSet):
    queryset = models.StepArtifact.objects.select_related("step")
    serializer_class = serializers.StepArtifactSerializer
    filterset_fields = ("step", "kind")

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user, uploaded_by=self.request.user)


class DesignBlockTemplateViewSet(viewsets.ModelViewSet):
    queryset = models.DesignBlockTemplate.objects.all()
    serializer_class = serializers.DesignBlockTemplateSerializer
    search_fields = ("name", "description", "version_tag")
    ordering_fields = ("name", "version_tag", "created_at")

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)


class BOMNodeViewSet(viewsets.ModelViewSet):
    queryset = models.BOMNode.objects.select_related("manufacturing_plan", "inventory_item", "parent")
    serializer_class = serializers.BOMNodeSerializer
    filterset_fields = ("manufacturing_plan", "parent", "inventory_item")
    ordering_fields = ("sequence", "created_at")

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)
        plan = serializer.instance.manufacturing_plan
        models.Quote.objects.filter(preliminary_manufacturing_plan=plan).update(needs_recalculation=True)


class MachineViewSet(viewsets.ModelViewSet):
    queryset = models.Machine.objects.all()
    serializer_class = serializers.MachineSerializer
    filterset_fields = ("state", "machine_type")
    search_fields = ("identifier", "name")
    ordering_fields = ("identifier", "name", "state")

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    @action(detail=True, methods=["post"], url_path="set-state")
    def set_state(self, request, pk=None):
        machine = self.get_object()
        new_state = request.data.get("state")
        if new_state not in dict(models.Machine.MachineState.choices):
            raise ValidationError(f"Invalid state: {new_state}")
        old = machine.state
        machine.state = new_state
        machine.updated_by = request.user
        machine.save()
        log_audit(
            user=request.user,
            action="machine_state_change",
            entity_type="Machine",
            entity_id=str(machine.id),
            before={"state": old},
            after={"state": new_state},
        )
        return Response(serializers.MachineSerializer(machine).data)

    @action(detail=True, methods=["get"], url_path="utilization")
    def utilization(self, request, pk=None):
        machine = self.get_object()
        active_maint = machine.maintenance_windows.filter(
            starts_at__lte=timezone.now(), ends_at__gte=timezone.now(), completed=False
        ).count()
        return Response({
            "identifier": machine.identifier,
            "state": machine.state,
            "capacity_hours_per_day": str(machine.capacity_hours_per_day),
            "scheduled_workload_hours": str(machine.scheduled_workload_hours),
            "actual_usage_hours": str(machine.actual_usage_hours),
            "utilization_pct": str(
                (machine.actual_usage_hours / machine.capacity_hours_per_day * 100).quantize(Decimal("0.01"))
                if machine.capacity_hours_per_day else Decimal("0")
            ),
            "active_maintenance_windows": active_maint,
        })


class MachineMaintenanceWindowViewSet(viewsets.ModelViewSet):
    queryset = models.MachineMaintenanceWindow.objects.select_related("machine")
    serializer_class = serializers.MachineMaintenanceWindowSerializer
    filterset_fields = ("machine", "completed", "blocks_scheduling")
    ordering_fields = ("starts_at", "ends_at")

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)


class WarehouseLocationViewSet(viewsets.ModelViewSet):
    queryset = models.WarehouseLocation.objects.all()
    serializer_class = serializers.WarehouseLocationSerializer
    filterset_fields = ("parent",)
    search_fields = ("code", "name")
    ordering_fields = ("code", "name")

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)


class InventoryItemViewSet(viewsets.ModelViewSet):
    queryset = models.InventoryItem.objects.select_related("location")
    serializer_class = serializers.InventoryItemSerializer
    filterset_fields = ("location", "status", "sku")
    search_fields = ("sku", "name", "batch_or_lot")
    ordering_fields = ("sku", "quantity", "created_at")

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    @action(detail=True, methods=["post"], url_path="adjust")
    def adjust_stock(self, request, pk=None):
        item = self.get_object()
        delta = Decimal(request.data.get("quantity_delta", "0"))
        movement_type = request.data.get("movement_type", "adjust")
        reference = request.data.get("reference", "")
        if movement_type not in dict(models.StockMovement.MovementType.choices):
            raise ValidationError(f"Invalid movement_type: {movement_type}")
        item.quantity += delta
        item.updated_by = request.user
        item.save()
        models.StockMovement.objects.create(
            inventory_item=item,
            movement_type=movement_type,
            quantity_delta=delta,
            reference=reference,
            performed_by=request.user,
            created_by=request.user,
            updated_by=request.user,
        )
        return Response(serializers.InventoryItemSerializer(item).data)


class CustomerOrderViewSet(RoleScopedMixin, viewsets.ModelViewSet):
    queryset = models.CustomerOrder.objects.select_related("customer", "source_quote")
    serializer_class = serializers.CustomerOrderSerializer
    filterset_fields = ("status", "customer", "source_quote")
    ordering_fields = ("order_number", "created_at", "delivery_deadline", "priority")
    search_fields = ("order_number", "notes")


class WorkOrderViewSet(viewsets.ModelViewSet):
    """Work orders are created via quote approval or `POST .../quotes/{id}/generate-work-order/`."""

    queryset = models.WorkOrder.objects.select_related("customer_order", "source_quote")
    serializer_class = serializers.WorkOrderSerializer
    http_method_names = ["get", "patch", "put", "head", "options"]
    filterset_fields = ("customer_order", "source_quote", "priority")
    ordering_fields = ("created_at", "delivery_deadline", "completion_percent", "wo_number")
    search_fields = ("wo_number",)

    @action(detail=True, methods=["post"], url_path="auto-schedule")
    def auto_schedule(self, request, pk=None):
        wo = self.get_object()
        results = auto_schedule_work_order(wo, request.user)
        return Response({"scheduled": len(results)})

    @action(detail=True, methods=["post"], url_path="generate-pick-list")
    def generate_pick_list(self, request, pk=None):
        wo = self.get_object()
        pl = create_pick_list_from_work_order(wo, request.user)
        return Response(serializers.PickListSerializer(pl).data, status=status.HTTP_201_CREATED)


class WorkOrderStepViewSet(viewsets.ModelViewSet):
    queryset = models.WorkOrderStep.objects.select_related("work_order", "machine")
    serializer_class = serializers.WorkOrderStepSerializer
    filterset_fields = ("work_order", "status", "machine")
    ordering_fields = ("sequence", "planned_start", "planned_end", "actual_start", "actual_end")

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)
        wo = serializer.instance.work_order
        steps = list(wo.steps.all())
        if steps:
            done = sum(1 for s in steps if s.status == models.WorkOrderStep.ExecutionStatus.COMPLETED)
            wo.completion_percent = (Decimal(done) / Decimal(len(steps)) * Decimal("100")).quantize(
                Decimal("0.01")
            )
            wo.save(update_fields=["completion_percent", "updated_at"])

    @action(detail=True, methods=["post"], url_path="start")
    def start_step(self, request, pk=None):
        step = self.get_object()
        if step.status not in (
            models.WorkOrderStep.ExecutionStatus.PENDING,
            models.WorkOrderStep.ExecutionStatus.READY,
        ):
            raise ValidationError("Step cannot be started from current status.")
        step.status = models.WorkOrderStep.ExecutionStatus.IN_PROGRESS
        step.actual_start = timezone.now()
        step.updated_by = request.user
        step.save()
        reserve_materials_for_step(step, request.user)
        log_audit(
            user=request.user,
            action="step_started",
            entity_type="WorkOrderStep",
            entity_id=str(step.id),
            after={"status": step.status, "actual_start": str(step.actual_start)},
        )
        return Response(serializers.WorkOrderStepSerializer(step).data)

    @action(detail=True, methods=["post"], url_path="complete")
    def complete_step(self, request, pk=None):
        step = self.get_object()
        if step.status != models.WorkOrderStep.ExecutionStatus.IN_PROGRESS:
            raise ValidationError("Only in-progress steps can be completed.")
        step.status = models.WorkOrderStep.ExecutionStatus.COMPLETED
        step.actual_end = timezone.now()
        step.updated_by = request.user
        step.save()
        wo = step.work_order
        steps = list(wo.steps.all())
        done = sum(1 for s in steps if s.status == models.WorkOrderStep.ExecutionStatus.COMPLETED)
        wo.completion_percent = (Decimal(done) / Decimal(len(steps)) * Decimal("100")).quantize(Decimal("0.01"))
        wo.save(update_fields=["completion_percent", "updated_at"])
        log_audit(
            user=request.user,
            action="step_completed",
            entity_type="WorkOrderStep",
            entity_id=str(step.id),
            after={"status": step.status, "actual_end": str(step.actual_end)},
        )
        return Response(serializers.WorkOrderStepSerializer(step).data)

    @action(detail=True, methods=["post"], url_path="block")
    def block_step(self, request, pk=None):
        step = self.get_object()
        step.status = models.WorkOrderStep.ExecutionStatus.BLOCKED
        step.issue_log = request.data.get("issue", step.issue_log)
        step.updated_by = request.user
        step.save()
        log_audit(
            user=request.user,
            action="step_blocked",
            entity_type="WorkOrderStep",
            entity_id=str(step.id),
            after={"status": step.status, "issue_log": step.issue_log},
        )
        return Response(serializers.WorkOrderStepSerializer(step).data)


class ScheduledStepViewSet(viewsets.ModelViewSet):
    queryset = models.ScheduledStep.objects.select_related("work_order_step", "machine")
    serializer_class = serializers.ScheduledStepSerializer
    filterset_fields = ("work_order_step", "machine", "manual_override")
    ordering_fields = ("planned_start", "planned_end")

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)


class ResourceEstimateViewSet(viewsets.ModelViewSet):
    queryset = models.ResourceEstimate.objects.select_related("manufacturing_plan")
    serializer_class = serializers.ResourceEstimateSerializer
    filterset_fields = ("manufacturing_plan",)
    ordering_fields = ("computed_at", "created_at")

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)


class QualityReportViewSet(viewsets.ModelViewSet):
    queryset = models.QualityReport.objects.select_related("work_order_step", "machine", "operator")
    serializer_class = serializers.QualityReportSerializer
    filterset_fields = ("work_order_step", "result", "machine", "operator")
    ordering_fields = ("created_at",)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)


class StoredFileViewSet(viewsets.ModelViewSet):
    queryset = models.StoredFile.objects.all()
    serializer_class = serializers.StoredFileSerializer
    search_fields = ("original_name", "version_label")
    ordering_fields = ("created_at",)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)


class InAppNotificationViewSet(viewsets.ModelViewSet):
    queryset = models.InAppNotification.objects.all()
    serializer_class = serializers.InAppNotificationSerializer
    http_method_names = ["get", "patch", "put", "head", "options"]
    filterset_fields = ("read", "event_code")
    ordering_fields = ("created_at",)

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.is_authenticated:
            return qs.filter(recipient=self.request.user)
        return qs.none()

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)


class AuditLogEntryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.AuditLogEntry.objects.all().order_by("-timestamp")
    serializer_class = serializers.AuditLogEntrySerializer
    filterset_fields = ("entity_type", "action", "user")
    ordering_fields = ("timestamp",)


class PermissionGrantViewSet(viewsets.ModelViewSet):
    queryset = models.PermissionGrant.objects.all()
    serializer_class = serializers.PermissionGrantSerializer
    filterset_fields = ("role", "entity")
    ordering_fields = ("role", "entity")

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)


class PickListViewSet(viewsets.ModelViewSet):
    queryset = models.PickList.objects.select_related("work_order")
    serializer_class = serializers.PickListSerializer
    filterset_fields = ("work_order", "status")
    ordering_fields = ("created_at", "code")

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)


class PickListLineViewSet(viewsets.ModelViewSet):
    queryset = models.PickListLine.objects.select_related("pick_list", "inventory_item")
    serializer_class = serializers.PickListLineSerializer
    filterset_fields = ("pick_list", "inventory_item")

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)


class StockMovementViewSet(viewsets.ModelViewSet):
    queryset = models.StockMovement.objects.select_related("inventory_item", "performed_by")
    serializer_class = serializers.StockMovementSerializer
    filterset_fields = ("inventory_item", "movement_type")
    ordering_fields = ("created_at",)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user, performed_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)


class UserProfileViewSet(viewsets.ModelViewSet):
    queryset = models.UserProfile.objects.select_related("user", "customer")
    serializer_class = serializers.UserProfileSerializer
    http_method_names = ["get", "patch", "put", "head", "options"]
    filterset_fields = ("role", "customer", "user")

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_superuser:
            return qs
        return qs.filter(user=user)
