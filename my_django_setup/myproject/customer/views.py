from django.shortcuts import render, get_object_or_404
from home.models import Order  # <-- Importing from home!

def customer_panel(request):
    """View for Customers to track orders via Order ID."""
    if request.method == 'POST':
        order_id = request.POST.get('order_id')
        order = get_object_or_404(Order, order_id=order_id)
        return render(request, 'customer/customer_tracking.html', {'order': order})
    
    return render(request, 'customer/customer_login.html')