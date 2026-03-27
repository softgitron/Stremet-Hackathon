from django.urls import path
from . import views

urlpatterns = [
    path('', views.manufacturer_panel, name='manufacturer_panel'),
]