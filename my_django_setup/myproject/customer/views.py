from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from core.models import (
    CustomerOrder,
    Quote,
    QuoteAttachment,
    QuoteLine,
    StoredFile,
    WorkOrder,
)
from core.models.base import UserRole
from core.services import save_quote_version


def _linked_customer(request):
    if not request.user.is_authenticated:
        return None
    profile = getattr(request.user, "stremet_profile", None)
    if not profile or not profile.customer_id:
        return None
    if profile.role != UserRole.CUSTOMER:
        return None
    return profile.customer


def customer_entry(request):
    if request.method == "POST":
        order_number = (request.POST.get("order_id") or "").strip()
        if not order_number:
            messages.error(request, "Please enter an order number.")
            return redirect("customer_panel")
        order = get_object_or_404(CustomerOrder, order_number=order_number)
        work_orders = WorkOrder.objects.filter(customer_order=order).order_by("-created_at")
        return render(
            request,
            "customer/customer_tracking.html",
            {"order": order, "work_orders": work_orders, "guest_lookup": True},
        )

    customer = _linked_customer(request)
    if customer:
        return customer_dashboard(request)
    return render(request, "customer/guest_entry.html")


def customer_dashboard(request):
    customer = _linked_customer(request)
    if customer is None:
        messages.info(
            request,
            "Log in with an account that has the Customer role and a linked company to see quotes and documents.",
        )
        return redirect("customer_panel")

    quotes = (
        Quote.objects.filter(customer=customer)
        .prefetch_related("lines")
        .order_by("-created_at")
    )
    orders = (
        CustomerOrder.objects.filter(customer=customer)
        .select_related("source_quote")
        .order_by("-created_at")
    )
    attachments = (
        QuoteAttachment.objects.filter(quote__customer=customer)
        .select_related("quote")
        .order_by("-created_at")[:50]
    )

    return render(
        request,
        "customer/dashboard.html",
        {
            "customer": customer,
            "quotes": quotes,
            "orders": orders,
            "attachments": attachments,
        },
    )


@login_required
def customer_upload_design(request):
    customer = _linked_customer(request)
    if customer is None:
        messages.warning(request, "Link your account to a customer record first.")
        return redirect("customer_panel")

    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        description = request.POST.get("description", "").strip()
        uploaded_file = request.FILES.get("design_file")

        if not title:
            messages.error(request, "Please provide a title for your request.")
            return redirect("customer_upload_design")

        import uuid
        quote_number = f"Q-SELF-{uuid.uuid4().hex[:8].upper()}"
        quote = Quote.objects.create(
            quote_number=quote_number,
            customer=customer,
            title=title,
            state=Quote.QuoteState.DRAFT,
            created_by=request.user,
            updated_by=request.user,
        )
        if description:
            QuoteLine.objects.create(
                quote=quote,
                description=description,
                quantity=1,
                unit_price=0,
                created_by=request.user,
                updated_by=request.user,
            )
        if uploaded_file:
            QuoteAttachment.objects.create(
                quote=quote,
                file=uploaded_file,
                original_name=uploaded_file.name,
                content_type=uploaded_file.content_type or "",
                uploaded_by=request.user,
                created_by=request.user,
                updated_by=request.user,
            )
            StoredFile.objects.create(
                file=uploaded_file,
                original_name=uploaded_file.name,
                tags=["customer_upload", "design"],
                version_label="1.0",
                created_by=request.user,
                updated_by=request.user,
            )
        save_quote_version(quote, request.user)
        messages.success(
            request,
            f"Design uploaded. Quote {quote_number} created in Draft state. Our team will review it shortly.",
        )
        return redirect("customer_dashboard")

    return render(request, "customer/upload_design.html", {"customer": customer})


@login_required
def customer_quote_detail(request, quote_id):
    customer = _linked_customer(request)
    if customer is None:
        messages.warning(
            request,
            "Your user is not linked to a customer record. Ask your administrator to assign a customer on your profile.",
        )
        return redirect("customer_panel")

    quote = get_object_or_404(
        Quote.objects.prefetch_related("lines").select_related("customer"),
        pk=quote_id,
        customer=customer,
    )
    transitions = quote.state_transitions.select_related("user").order_by("transitioned_at")
    attachments = quote.attachments.select_related("uploaded_by").order_by("-created_at")

    return render(
        request,
        "customer/quote_detail.html",
        {
            "customer": customer,
            "quote": quote,
            "transitions": transitions,
            "attachments": attachments,
        },
    )


@login_required
def customer_order_detail(request, order_number):
    customer = _linked_customer(request)
    if customer is None:
        messages.warning(
            request,
            "Your user is not linked to a customer record. Ask your administrator to assign a customer on your profile.",
        )
        return redirect("customer_panel")

    order = get_object_or_404(
        CustomerOrder.objects.select_related("customer", "source_quote"),
        order_number=order_number,
        customer=customer,
    )
    work_orders = WorkOrder.objects.filter(customer_order=order).select_related("source_quote").order_by(
        "-created_at"
    )

    return render(
        request,
        "customer/order_detail.html",
        {
            "customer": customer,
            "order": order,
            "work_orders": work_orders,
        },
    )
