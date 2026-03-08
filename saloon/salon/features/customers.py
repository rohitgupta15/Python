from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render
from django.utils import timezone

from ..forms import CustomerForm
from .helpers import get_approved_owner_salon
from .loyalty import award_referral_bonus

PAGE_SIZE_OPTIONS = (10, 20, 50)


def _resolve_page_size(raw_value):
    try:
        value = int(raw_value or 20)
    except (TypeError, ValueError):
        value = 20
    if value not in PAGE_SIZE_OPTIONS:
        value = 20
    return value


@login_required
def salon_customers(request, slug):
    salon = get_approved_owner_salon(request, slug)
    form = CustomerForm(request.POST or None, salon=salon)

    if request.method == "POST":
        form_type = request.POST.get("form_type")
        if form_type == "add_customer" and form.is_valid():
            customer = form.save(commit=False)
            customer.salon = salon
            if not customer.whatsapp_number:
                customer.whatsapp_number = customer.phone
            customer.save()
            award_referral_bonus(customer)
            messages.success(request, "Customer added.")
            return redirect("salon_customers", slug=salon.slug)
        if form_type == "add_customer" and not form.is_valid():
            phone_errors = form.errors.get("phone", [])
            if any("already exists" in str(err).lower() for err in phone_errors):
                messages.error(request, "Duplicate mobile number. This customer already exists.")
        if form_type == "delete_customer":
            messages.error(
                request,
                "Customer deletion is disabled in customer history. Contact admin if removal is required.",
            )
            return redirect("salon_customers", slug=salon.slug)

    search = request.GET.get("q", "").strip()
    tier = request.GET.get("tier", "").strip()
    page_size = _resolve_page_size(request.GET.get("page_size"))
    customers = salon.customers.all()
    if search:
        customers = customers.filter(Q(full_name__icontains=search) | Q(phone__icontains=search))
    if tier == "vip":
        customers = customers.filter(is_vip=True)
    elif tier == "high_spend":
        customers = customers.filter(total_spend__gte=2000)
    elif tier == "inactive":
        cutoff = timezone.localdate() - timedelta(days=60)
        customers = customers.filter(Q(last_visit__lt=cutoff) | Q(last_visit__isnull=True))
    customers = customers.order_by("-created_at")

    customer_page = request.GET.get("page") or "1"
    customers = Paginator(customers, page_size).get_page(customer_page)
    customer_query_params = request.GET.copy()
    customer_query_params.pop("page", None)
    customer_querystring = customer_query_params.urlencode()

    top_customers = salon.customers.order_by("-total_spend", "-total_visits")[:5]
    context = {
        "salon": salon,
        "form": form,
        "customers": customers,
        "top_customers": top_customers,
        "search": search,
        "tier": tier,
        "customer_querystring": customer_querystring,
        "page_size": page_size,
        "page_size_options": PAGE_SIZE_OPTIONS,
    }
    return render(request, "salon/salon_customers.html", context)
