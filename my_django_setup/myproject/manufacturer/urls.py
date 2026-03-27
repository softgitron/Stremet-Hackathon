from django.urls import path

from . import views

urlpatterns = [
    path("", views.manufacturer_panel, name="manufacturer_panel"),
    path("work-order/<uuid:wo_id>/", views.work_order_detail, name="manufacturer_wo_detail"),
]
