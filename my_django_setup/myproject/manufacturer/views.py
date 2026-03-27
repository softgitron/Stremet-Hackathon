from django.shortcuts import render
from home.models import Order  # <-- Importing from home!

def manufacturer_panel(request):
    """View for Manufacturers to update stages and view client logs."""
    active_orders = Order.objects.exclude(status='delivered')
    return render(request, 'manufacturer/manufacturer_panel.html', {'orders': active_orders})