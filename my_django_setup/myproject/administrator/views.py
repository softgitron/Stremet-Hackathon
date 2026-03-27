from django.shortcuts import render, redirect
from django.contrib import messages
from home.models import Order, Client, OrderImage  # <-- Importing from home!

def admin_panel(request):
    """View for Administrators to add and manage orders."""
    if request.method == 'POST':
        try:
            # 1. Handle Client Data
            company_name = request.POST.get('company_name')
            client_email = request.POST.get('client_email')
            
            client, created = Client.objects.get_or_create(
                email=client_email,
                defaults={'company_name': company_name}
            )

            # 2. Compile Dimensions safely (handling empty strings)
            thickness = request.POST.get('dim_thickness') or '0'
            width = request.POST.get('dim_width') or '0'
            length = request.POST.get('dim_length') or '0'
            dimensions_str = f"{thickness}mm x {width}mm x {length}mm"

            # 3. Handle numbers and dates safely
            # If the user leaves quantity blank, default to 0 to prevent crashes
            qty = request.POST.get('quantity_tons')
            if not qty:
                qty = 0

            # 4. Create the Order
            new_order = Order.objects.create(
                order_id=request.POST.get('order_id'),
                client=client,
                target_delivery=request.POST.get('target_delivery'),
                steel_grade=request.POST.get('steel_grade'),
                product_form=request.POST.get('product_form'),
                dimensions=dimensions_str,
                quantity_tons=qty,
                surface_finish=request.POST.get('surface_finish'),
                
                heat_treatment=(request.POST.get('heat_treatment') == 'yes'),
                ultrasonic_test=(request.POST.get('ultrasonic_test') == 'yes'),
                mill_certificate=(request.POST.get('mill_certificate') == 'yes'),
                
                blueprint_file=request.FILES.get('blueprint_file'),
                admin_notes=request.POST.get('admin_notes')
            )

            # 5. Handle Multiple Image Uploads
            images = request.FILES.getlist('reference_images')
            for img in images:
                OrderImage.objects.create(order=new_order, image=img)

            # Success! Tell the user and redirect
            messages.success(request, f"Order {new_order.order_id} successfully created!")
            return redirect('home_dashboard')

        except Exception as e:
            # THIS IS THE MAGIC FIX: If it fails, print the exact reason to the terminal
            print(f"\n--- DATABASE SAVE ERROR ---\n{e}\n---------------------------\n")
            messages.error(request, f"Error saving order: {e}")
            return redirect('admin_panel')

    # If GET request, just show the empty form
    return render(request, 'administrator/admin_panel.html')