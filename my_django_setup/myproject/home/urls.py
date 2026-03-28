from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="home_dashboard"),
    # Sales
    path("portal/sales/", views.portal_sales, name="portal_sales"),
    path("portal/sales/create-quote/", views.sales_create_quote, name="sales_create_quote"),
    path("portal/sales/quote/<uuid:quote_id>/", views.sales_quote_detail, name="sales_quote_detail"),
    path("portal/sales/design-request/", views.sales_create_design_request, name="sales_create_design_request"),
    # Design
    path("portal/design/", views.portal_design, name="portal_design"),
    path("portal/design/create-plan/", views.design_create_plan, name="design_create_plan"),
    path("portal/design/plan/<uuid:plan_id>/", views.design_plan_detail, name="design_plan_detail"),
    path("portal/design/create-block/", views.design_create_block, name="design_create_block"),
    # Warehouse
    path("portal/warehouse/", views.portal_warehouse, name="portal_warehouse"),
    path("portal/warehouse/create-location/", views.warehouse_create_location, name="warehouse_create_location"),
    path("portal/warehouse/create-item/", views.warehouse_create_item, name="warehouse_create_item"),
    path("portal/warehouse/adjust/<uuid:item_id>/", views.warehouse_adjust_stock, name="warehouse_adjust_stock"),
    # Ops Admin
    path("portal/ops/", views.portal_admin, name="portal_admin"),
    path("portal/ops/create-customer/", views.admin_create_customer, name="admin_create_customer"),
    path("portal/ops/create-machine/", views.admin_create_machine, name="admin_create_machine"),
    path("portal/ops/create-part/", views.admin_create_part, name="admin_create_part"),
]
