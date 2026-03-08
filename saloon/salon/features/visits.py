from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.shortcuts import redirect, render

from ..forms import SalonVisitForm
from .helpers import get_approved_owner_salon
from .loyalty import apply_loyalty_for_visit

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
def salon_visits(request, slug):
    salon = get_approved_owner_salon(request, slug)
    form = SalonVisitForm(request.POST or None, salon=salon)
    if request.method == "POST" and form.is_valid():
        visit = form.save(commit=False)
        visit.salon = salon
        visit.save()
        form.save_m2m()
        apply_loyalty_for_visit(visit)
        messages.success(request, "Visit saved and customer history updated.")
        return redirect("salon_visits", slug=salon.slug)

    search = (request.GET.get("q") or "").strip()
    page_size = _resolve_page_size(request.GET.get("page_size"))
    visits_qs = salon.visits.select_related("customer", "service", "offer", "assigned_worker").prefetch_related("services")
    if search:
        visits_qs = visits_qs.filter(
            Q(customer__full_name__icontains=search)
            | Q(customer__phone__icontains=search)
            | Q(service__name__icontains=search)
            | Q(services__name__icontains=search)
            | Q(assigned_worker__full_name__icontains=search)
        ).distinct()
    visits_qs = visits_qs.order_by("-visit_date", "-id")
    visit_page = request.GET.get("page") or "1"
    visits = Paginator(visits_qs, page_size).get_page(visit_page)
    visit_query_params = request.GET.copy()
    visit_query_params.pop("page", None)
    visit_querystring = visit_query_params.urlencode()

    total_revenue = salon.visits.aggregate(total=Sum("amount_paid")).get("total") or 0
    visit_rows = []
    for visit in visits:
        worker_payout = 0
        owner_share = visit.amount_paid
        if visit.assigned_worker and visit.assigned_worker.payment_mode == "commission":
            worker_payout = (visit.amount_paid * visit.assigned_worker.commission_percent) / 100
            owner_share = visit.amount_paid - worker_payout
        visit_rows.append(
            {
                "visit": visit,
                "service_names": visit.service_names_display,
                "worker_payout": worker_payout,
                "owner_share": owner_share,
            }
        )

    context = {
        "salon": salon,
        "form": form,
        "visits": visits,
        "visit_rows": visit_rows,
        "total_revenue": total_revenue,
        "search": search,
        "page_size": page_size,
        "page_size_options": PAGE_SIZE_OPTIONS,
        "visit_querystring": visit_querystring,
    }
    return render(request, "salon/salon_visits.html", context)
