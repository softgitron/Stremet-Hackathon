from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r"customers", views.CustomerViewSet, basename="customer")
router.register(r"parts", views.PartViewSet, basename="part")
router.register(r"quotes", views.QuoteViewSet, basename="quote")
router.register(r"quote-lines", views.QuoteLineViewSet, basename="quoteline")
router.register(r"quote-transitions", views.QuoteStateTransitionViewSet, basename="quotetransition")
router.register(r"quote-threads", views.QuoteDiscussionThreadViewSet, basename="quotethread")
router.register(r"quote-comments", views.QuoteCommentViewSet, basename="quotecomment")
router.register(r"quote-attachments", views.QuoteAttachmentViewSet, basename="quoteattachment")
router.register(r"quote-versions", views.QuoteVersionViewSet, basename="quoteversion")
router.register(r"quote-costs", views.QuoteCostBreakdownViewSet, basename="quotecost")
router.register(r"design-support", views.DesignSupportRequestViewSet, basename="designsupport")
router.register(r"design-support-files", views.DesignSupportAttachmentViewSet, basename="designsupportfile")
router.register(r"manufacturing-plans", views.ManufacturingPlanViewSet, basename="mfgplan")
router.register(r"manufacturing-steps", views.ManufacturingStepViewSet, basename="mfgstep")
router.register(r"step-artifacts", views.StepArtifactViewSet, basename="stepartifact")
router.register(r"design-blocks", views.DesignBlockTemplateViewSet, basename="designblock")
router.register(r"bom-nodes", views.BOMNodeViewSet, basename="bomnode")
router.register(r"machines", views.MachineViewSet, basename="machine")
router.register(r"machine-maintenance", views.MachineMaintenanceWindowViewSet, basename="machinemaint")
router.register(r"warehouse-locations", views.WarehouseLocationViewSet, basename="warehouse")
router.register(r"inventory-items", views.InventoryItemViewSet, basename="inventory")
router.register(r"orders", views.CustomerOrderViewSet, basename="order")
router.register(r"work-orders", views.WorkOrderViewSet, basename="workorder")
router.register(r"work-order-steps", views.WorkOrderStepViewSet, basename="workorderstep")
router.register(r"scheduled-steps", views.ScheduledStepViewSet, basename="scheduledstep")
router.register(r"resource-estimates", views.ResourceEstimateViewSet, basename="resourceestimate")
router.register(r"quality-reports", views.QualityReportViewSet, basename="quality")
router.register(r"stored-files", views.StoredFileViewSet, basename="storedfile")
router.register(r"notifications", views.InAppNotificationViewSet, basename="notification")
router.register(r"audit-log", views.AuditLogEntryViewSet, basename="auditlog")
router.register(r"permissions", views.PermissionGrantViewSet, basename="permission")
router.register(r"pick-lists", views.PickListViewSet, basename="picklist")
router.register(r"pick-list-lines", views.PickListLineViewSet, basename="picklistline")
router.register(r"stock-movements", views.StockMovementViewSet, basename="stockmovement")
router.register(r"user-profiles", views.UserProfileViewSet, basename="userprofile")

urlpatterns = [
    path("", include(router.urls)),
]
