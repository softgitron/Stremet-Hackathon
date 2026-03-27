from django.contrib import admin

from . import models

for model in (
    models.Customer,
    models.CustomerOrder,
    models.Part,
    models.Quote,
    models.QuoteLine,
    models.QuoteStateTransition,
    models.ManufacturingPlan,
    models.ManufacturingStep,
    models.Machine,
    models.InventoryItem,
    models.WarehouseLocation,
    models.WorkOrder,
    models.WorkOrderStep,
    models.UserProfile,
    models.PermissionGrant,
):
    admin.site.register(model)
