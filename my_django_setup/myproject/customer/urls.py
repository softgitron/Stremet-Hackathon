from django.urls import path

from . import views

urlpatterns = [
    path("", views.customer_entry, name="customer_panel"),
    path("dashboard/", views.customer_dashboard, name="customer_dashboard"),
    path("quotes/<uuid:quote_id>/", views.customer_quote_detail, name="customer_quote_detail"),
    path("orders/<str:order_number>/", views.customer_order_detail, name="customer_order_detail"),
]