from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="home_dashboard"),
    path("portal/sales/", views.portal_sales, name="portal_sales"),
    path("portal/design/", views.portal_design, name="portal_design"),
    path("portal/warehouse/", views.portal_warehouse, name="portal_warehouse"),
    path("portal/ops/", views.portal_admin, name="portal_admin"),
]