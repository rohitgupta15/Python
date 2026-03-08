from datetime import timedelta
import re

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date

from ..workers.forms import WorkerVisitForm
from ..forms import CustomerForm
from ..models import Worker
from .loyalty import award_referral_bonus
from .loyalty import apply_loyalty_for_visit

HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
PAGE_SIZE = 10


def _get_logged_worker(user):
    return (
        Worker.objects.select_related("salon")
        .filter(user=user, can_login=True, is_active=True, is_deleted=False, salon__is_active=True)
        .first()
    )


def _to_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@login_required
def worker_dashboard(request):
    worker = _get_logged_worker(request.user)
    if not worker:
        messages.error(request, "Worker access is not enabled for this account.")
        return redirect("owner_dashboard")

    today = timezone.localdate()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)

    day_stats = worker.visits.filter(visit_date=today).aggregate(
        visits=Count("id"),
        customers=Count("customer", distinct=True),
        revenue=Sum("amount_paid"),
    )
    week_stats = worker.visits.filter(visit_date__range=(week_start, today)).aggregate(
        visits=Count("id"),
        customers=Count("customer", distinct=True),
        revenue=Sum("amount_paid"),
    )
    month_stats = worker.visits.filter(visit_date__range=(month_start, today)).aggregate(
        visits=Count("id"),
        customers=Count("customer", distinct=True),
        revenue=Sum("amount_paid"),
    )
    recent_visits_qs = (
        worker.visits.select_related("customer", "service")
        .prefetch_related("services")
        .order_by("-visit_date", "-id")
    )
    recent_page = request.GET.get("recent_page") or "1"
    recent_visits = Paginator(recent_visits_qs, PAGE_SIZE).get_page(recent_page)
    recent_query_params = request.GET.copy()
    recent_query_params.pop("recent_page", None)

    context = {
        "worker": worker,
        "salon": worker.salon,
        "day_stats": day_stats,
        "week_stats": week_stats,
        "month_stats": month_stats,
        "recent_visits": recent_visits,
        "recent_querystring": recent_query_params.urlencode(),
    }
    return render(request, "salon/worker_dashboard.html", context)


@login_required
def worker_salary_slips(request):
    worker = _get_logged_worker(request.user)
    if not worker:
        messages.error(request, "Worker access is not enabled for this account.")
        return redirect("owner_dashboard")

    today = timezone.localdate()
    selected_year = _to_int(request.GET.get("year"), today.year)
    selected_month = _to_int(request.GET.get("month"), today.month)
    if selected_month < 1 or selected_month > 12:
        selected_month = today.month

    yearly_payments = worker.salary_payments.filter(period_year=selected_year).order_by(
        "-period_year",
        "-period_month",
        "-paid_on",
        "-id",
    )
    monthly_payments = yearly_payments.filter(period_month=selected_month)
    slips_page = request.GET.get("slips_page") or "1"
    slips = Paginator(monthly_payments, PAGE_SIZE).get_page(slips_page)
    slips_query_params = request.GET.copy()
    slips_query_params.pop("slips_page", None)

    yearly_total = yearly_payments.aggregate(total=Sum("amount_paid")).get("total") or 0
    monthly_total = monthly_payments.aggregate(total=Sum("amount_paid")).get("total") or 0
    monthly_summary = (
        yearly_payments.values("period_month")
        .annotate(total_paid=Sum("amount_paid"), payments=Count("id"))
        .order_by("period_month")
    )

    context = {
        "worker": worker,
        "salon": worker.salon,
        "selected_year": selected_year,
        "selected_month": selected_month,
        "yearly_total": yearly_total,
        "monthly_total": monthly_total,
        "monthly_summary": monthly_summary,
        "slips": slips,
        "slips_querystring": slips_query_params.urlencode(),
        "year_choices": range(today.year - 5, today.year + 1),
    }
    return render(request, "salon/worker_salary_slips.html", context)


@login_required
def worker_visit_entry(request):
    worker = _get_logged_worker(request.user)
    if not worker:
        messages.error(request, "Worker access is not enabled for this account.")
        return redirect("owner_dashboard")

    form = WorkerVisitForm(request.POST or None, salon=worker.salon)
    if request.method == "POST" and form.is_valid():
        visit = form.save(commit=False)
        visit.salon = worker.salon
        visit.assigned_worker = worker
        visit.save()
        form.save_m2m()
        apply_loyalty_for_visit(visit)
        messages.success(request, "Visit saved successfully.")
        return redirect("worker_visit_entry")

    filter_mode = (request.GET.get("filter") or "monthly").strip().lower()
    if filter_mode not in {"weekly", "monthly", "range"}:
        filter_mode = "monthly"
    date_from = (request.GET.get("date_from") or "").strip()
    date_to = (request.GET.get("date_to") or "").strip()
    today = timezone.localdate()
    filter_start = None
    filter_end = today
    if filter_mode == "weekly":
        filter_start = today - timedelta(days=today.weekday())
    elif filter_mode == "monthly":
        filter_start = today.replace(day=1)
    else:
        parsed_from = parse_date(date_from) if date_from else None
        parsed_to = parse_date(date_to) if date_to else None
        if parsed_from and parsed_to and parsed_from > parsed_to:
            parsed_from, parsed_to = parsed_to, parsed_from
            date_from, date_to = parsed_from.isoformat(), parsed_to.isoformat()
        if parsed_from and parsed_to:
            filter_start, filter_end = parsed_from, parsed_to
        elif parsed_from:
            filter_start = parsed_from
        elif parsed_to:
            filter_start, filter_end = parsed_to, parsed_to
        else:
            filter_mode = "monthly"
            filter_start = today.replace(day=1)

    visits_qs = (
        worker.visits.select_related("customer", "service", "offer")
        .prefetch_related("services")
    )
    if filter_start:
        visits_qs = visits_qs.filter(visit_date__range=(filter_start, filter_end))
    visits_qs = visits_qs.order_by("-visit_date", "-id")
    summary = visits_qs.aggregate(
        total_visits=Count("id"),
        total_customers=Count("customer", distinct=True),
        total_revenue=Sum("amount_paid"),
    )
    visits_page = request.GET.get("visits_page") or "1"
    visits = Paginator(visits_qs, PAGE_SIZE).get_page(visits_page)
    visits_query_params = request.GET.copy()
    visits_query_params.pop("visits_page", None)
    return render(
        request,
        "salon/worker_visit_entry.html",
        {
            "worker": worker,
            "salon": worker.salon,
            "form": form,
            "visits": visits,
            "visits_querystring": visits_query_params.urlencode(),
            "filter_mode": filter_mode,
            "date_from": date_from,
            "date_to": date_to,
            "filter_start": filter_start,
            "filter_end": filter_end,
            "summary": summary,
        },
    )


@login_required
def worker_customer_search(request):
    worker = _get_logged_worker(request.user)
    if not worker:
        return JsonResponse({"results": []}, status=403)

    query = (request.GET.get("q") or "").strip()
    if not query:
        return JsonResponse({"results": []})

    customers = (
        worker.salon.customers.filter(
            Q(full_name__icontains=query)
            | Q(phone__icontains=query)
            | Q(whatsapp_number__icontains=query)
        )
        .order_by("full_name")[:15]
    )
    results = []
    for customer in customers:
        name = customer.full_name or "Customer"
        display = name if not customer.phone else f"{name} ({customer.phone})"
        results.append(
            {
                "id": customer.id,
                "display": display,
                "phone": customer.phone or "",
                "whatsapp": customer.whatsapp_number or "",
                "points": customer.loyalty_points or 0,
            }
        )
    return JsonResponse({"results": results})


@login_required
def worker_service_search(request):
    worker = _get_logged_worker(request.user)
    if not worker:
        return JsonResponse({"results": []}, status=403)

    query = (request.GET.get("q") or "").strip()
    if not query:
        return JsonResponse({"results": []})

    services = (
        worker.salon.services.filter(is_active=True, name__icontains=query)
        .order_by("name")[:15]
    )
    results = [
        {
            "id": service.id,
            "name": service.name,
            "category": service.category or "",
            "price": str(service.price),
        }
        for service in services
    ]
    return JsonResponse({"results": results})


@login_required
def worker_customers(request):
    worker = _get_logged_worker(request.user)
    if not worker:
        messages.error(request, "Worker access is not enabled for this account.")
        return redirect("owner_dashboard")

    form = CustomerForm(request.POST or None, salon=worker.salon)
    if request.method == "POST":
        if form.is_valid():
            customer = form.save(commit=False)
            customer.salon = worker.salon
            if not customer.whatsapp_number:
                customer.whatsapp_number = customer.phone
            customer.save()
            award_referral_bonus(customer)
            messages.success(request, "Customer registered successfully.")
            return redirect("worker_customers")
        messages.error(request, "Validation failed. Please correct customer registration details.")

    search = (request.GET.get("q") or "").strip()
    customers = worker.salon.customers.order_by("-created_at")
    if search:
        customers = customers.filter(Q(full_name__icontains=search) | Q(phone__icontains=search))

    customer_page = request.GET.get("customer_page") or "1"
    customers = Paginator(customers, PAGE_SIZE).get_page(customer_page)
    customer_query_params = request.GET.copy()
    customer_query_params.pop("customer_page", None)

    return render(
        request,
        "salon/worker_customers.html",
        {
            "worker": worker,
            "salon": worker.salon,
            "form": form,
            "customers": customers,
            "search": search,
            "customer_querystring": customer_query_params.urlencode(),
        },
    )


@login_required
def worker_nav_color_update(request):
    if request.method != "POST":
        return redirect("worker_dashboard")

    worker = _get_logged_worker(request.user)
    if not worker:
        messages.error(request, "Worker access is not enabled for this account.")
        return redirect("owner_dashboard")

    nav_color = (request.POST.get("nav_color") or "").strip()
    nav_background_color = (request.POST.get("nav_background_color") or "").strip()
    nav_text_color = (request.POST.get("nav_text_color") or "").strip()
    next_url = (request.POST.get("next") or "").strip()

    if not (
        HEX_COLOR_RE.match(nav_color)
        and HEX_COLOR_RE.match(nav_background_color)
        and HEX_COLOR_RE.match(nav_text_color)
    ):
        messages.error(request, "Please select a valid color.")
    else:
        worker.nav_color = nav_color
        worker.nav_background_color = nav_background_color
        worker.nav_text_color = nav_text_color
        worker.save(update_fields=["nav_color", "nav_background_color", "nav_text_color"])
        messages.success(request, "Menu style updated.")

    if next_url.startswith("/"):
        return redirect(next_url)
    return redirect("worker_dashboard")
