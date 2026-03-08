import calendar
from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from ..workers.forms import WorkerForm, WorkerSalaryPaymentForm
from ..workers.services import build_worker_cards, parse_month_key
from ..models import Worker
from .helpers import get_approved_owner_salon

username_validator = UnicodeUsernameValidator()
PAGE_SIZE_OPTIONS = (10, 20, 50)


def _owner_attempted_kyc_doc_change(request):
    if request.FILES.get("pan_image") or request.FILES.get("aadhaar_image"):
        return True
    if request.POST.get("pan_image-clear") or request.POST.get("aadhaar_image-clear"):
        return True
    return False


def _resolve_page_size(raw_value):
    try:
        value = int(raw_value or 10)
    except (TypeError, ValueError):
        value = 10
    if value not in PAGE_SIZE_OPTIONS:
        value = 10
    return value


@login_required
def salon_workers(request, slug):
    salon = get_approved_owner_salon(request, slug)
    selected_month = (request.GET.get("month") or datetime.now().strftime("%Y-%m")).strip()
    snapshot = (request.GET.get("snapshot") or "daily").strip().lower()
    worker_search = (request.GET.get("worker_q") or "").strip()
    worker_mode = (request.GET.get("worker_mode") or "").strip().lower()
    worker_access = (request.GET.get("worker_access") or "").strip().lower()
    page_size = _resolve_page_size(request.GET.get("page_size"))
    if snapshot not in {"daily", "weekly"}:
        snapshot = "daily"
    if worker_mode not in {"fixed", "commission"}:
        worker_mode = ""
    if worker_access not in {"enabled", "disabled"}:
        worker_access = ""
    year, month = parse_month_key(selected_month)
    month_start = datetime(year, month, 1).date()
    month_end_day = calendar.monthrange(year, month)[1]
    month_end = datetime(year, month, month_end_day).date()

    worker_form = WorkerForm(request.POST or None)
    salary_form = WorkerSalaryPaymentForm(
        request.POST or None,
        salon=salon,
        initial={"period_month": month, "period_year": year},
    )

    if request.method == "POST":
        if _owner_attempted_kyc_doc_change(request):
            messages.error(
                request,
                "KYC document images (PAN/Aadhaar) are admin-managed only. Please contact admin for upload/update.",
            )
            return redirect("salon_workers", slug=salon.slug)

        form_type = request.POST.get("form_type")
        if form_type == "add_worker":
            worker_form = WorkerForm(request.POST)
            if worker_form.is_valid():
                worker = worker_form.save(commit=False)
                worker.salon = salon
                worker.save()
                messages.success(request, "Worker added.")
                return redirect("salon_workers", slug=salon.slug)
            messages.error(request, "Validation failed. Please correct worker registration fields.")
        elif form_type == "grant_worker_access":
            worker = get_object_or_404(Worker, id=request.POST.get("worker_id"), salon=salon, is_deleted=False)
            username = (request.POST.get("username") or "").strip()
            password = (request.POST.get("password") or "").strip()
            if not username:
                messages.error(request, "Username is required to provide worker access.")
                return redirect("salon_workers", slug=salon.slug)
            if len(username) > 150:
                messages.error(request, "Username must be at most 150 characters.")
                return redirect("salon_workers", slug=salon.slug)
            try:
                username_validator(username)
            except ValidationError:
                messages.error(request, "Username contains invalid characters.")
                return redirect("salon_workers", slug=salon.slug)

            existing_user = User.objects.filter(username=username).exclude(pk=getattr(worker.user, "pk", None)).first()
            if existing_user:
                messages.error(request, "Username already exists. Please use a different username.")
                return redirect("salon_workers", slug=salon.slug)

            target_user = worker.user or User(username=username)
            target_user.username = username
            if password:
                try:
                    validate_password(password, user=target_user)
                except ValidationError as exc:
                    messages.error(request, " ".join(exc.messages))
                    return redirect("salon_workers", slug=salon.slug)

            if worker.user:
                worker.user.username = username
                worker.user.is_active = True
                if password:
                    worker.user.set_password(password)
                worker.user.save()
            else:
                if not password:
                    messages.error(request, "Password is required for first-time worker access setup.")
                    return redirect("salon_workers", slug=salon.slug)
                user = User.objects.create_user(username=username, password=password)
                worker.user = user
            worker.can_login = True
            worker.is_active = True
            worker.save(update_fields=["user", "can_login", "is_active"])
            messages.success(request, f"Portal access enabled for {worker.full_name}.")
            return redirect("salon_workers", slug=salon.slug)
        elif form_type == "disable_worker_access":
            worker = get_object_or_404(Worker, id=request.POST.get("worker_id"), salon=salon)
            worker.can_login = False
            if worker.user:
                worker.user.is_active = False
                worker.user.save(update_fields=["is_active"])
            worker.save(update_fields=["can_login"])
            messages.success(request, f"Portal access disabled for {worker.full_name}.")
            return redirect("salon_workers", slug=salon.slug)
        elif form_type == "delete_worker":
            worker = get_object_or_404(Worker, id=request.POST.get("worker_id"), salon=salon)
            worker.is_deleted = True
            worker.deleted_at = timezone.now()
            worker.is_active = False
            worker.can_login = False
            if worker.user:
                worker.user.is_active = False
                worker.user.save(update_fields=["is_active"])
            worker.save(update_fields=["is_deleted", "deleted_at", "is_active", "can_login"])
            messages.success(request, "Worker archived. Admin can still audit this record.")
            return redirect("salon_workers", slug=salon.slug)
        elif form_type == "add_salary_payment":
            salary_form = WorkerSalaryPaymentForm(request.POST, salon=salon)
            if salary_form.is_valid():
                payment = salary_form.save(commit=False)
                payment.salon = salon
                payment.save()
                messages.success(request, "Salary payment entry added.")
                return redirect("salon_workers", slug=salon.slug)
            messages.error(request, "Validation failed. Please correct salary payment fields.")

    workers = salon.workers.filter(is_deleted=False)
    if worker_search:
        workers = workers.filter(
            Q(full_name__icontains=worker_search)
            | Q(role__icontains=worker_search)
            | Q(phone__icontains=worker_search)
            | Q(pan_number__icontains=worker_search)
            | Q(aadhaar_number__icontains=worker_search)
            | Q(city__icontains=worker_search)
            | Q(state__icontains=worker_search)
            | Q(pincode__icontains=worker_search)
            | Q(user__username__icontains=worker_search)
        )
    if worker_mode:
        workers = workers.filter(payment_mode=worker_mode)
    if worker_access == "enabled":
        workers = workers.filter(can_login=True)
    elif worker_access == "disabled":
        workers = workers.filter(can_login=False)
    workers = workers.order_by("full_name")

    salary_payments_qs = salon.worker_salary_payments.filter(period_year=year, period_month=month).select_related("worker")
    active_incentive_campaigns = salon.worker_incentive_campaigns.filter(
        is_active=True,
        valid_from__lte=month_end,
        valid_to__gte=month_start,
    ).order_by("-bonus_percent", "-created_at")
    worker_cards = build_worker_cards(
        salon,
        workers,
        salary_payments_qs,
        year,
        month,
        incentive_campaigns=active_incentive_campaigns,
    )
    worker_page = request.GET.get("worker_page") or "1"
    worker_cards = Paginator(worker_cards, page_size).get_page(worker_page)
    worker_list_query_params = request.GET.copy()
    worker_list_query_params.pop("worker_page", None)
    worker_list_querystring = worker_list_query_params.urlencode()
    salary_page = request.GET.get("salary_page") or "1"
    salary_payments = Paginator(salary_payments_qs, page_size).get_page(salary_page)
    salary_query_params = request.GET.copy()
    salary_query_params.pop("salary_page", None)
    salary_querystring = salary_query_params.urlencode()

    today = timezone.localdate()
    if snapshot == "weekly":
        snapshot_start = today - timedelta(days=today.weekday())
    else:
        snapshot_start = today
    worker_snapshot = (
        salon.visits.filter(assigned_worker__isnull=False, visit_date__range=(snapshot_start, today))
        .values("assigned_worker__full_name")
        .annotate(
            visit_count=Count("id"),
            customer_count=Count("customer", distinct=True),
            total_revenue=Sum("amount_paid"),
        )
        .order_by("-visit_count", "assigned_worker__full_name")
    )
    summary_totals = {
        "total_visits": sum(item["visit_count"] for item in worker_snapshot),
        "total_customers": sum(item["customer_count"] for item in worker_snapshot),
        "total_revenue": sum((item["total_revenue"] or 0) for item in worker_snapshot),
    }
    month_cutoff = today - timedelta(days=180)
    monthly_progress = (
        salon.visits.filter(assigned_worker__isnull=False, visit_date__gte=month_cutoff)
        .annotate(month=TruncMonth("visit_date"))
        .values("month", "assigned_worker__full_name")
        .annotate(
            visit_count=Count("id"),
            customer_count=Count("customer", distinct=True),
            total_revenue=Sum("amount_paid"),
        )
        .order_by("-month", "assigned_worker__full_name")
    )
    progress_page = request.GET.get("progress_page") or "1"
    monthly_progress = Paginator(monthly_progress, page_size).get_page(progress_page)
    progress_query_params = request.GET.copy()
    progress_query_params.pop("progress_page", None)
    progress_querystring = progress_query_params.urlencode()

    context = {
        "salon": salon,
        "worker_form": worker_form,
        "salary_form": salary_form,
        "workers": workers,
        "worker_cards": worker_cards,
        "salary_payments": salary_payments,
        "selected_month": f"{year:04d}-{month:02d}",
        "snapshot": snapshot,
        "worker_search": worker_search,
        "worker_mode": worker_mode,
        "worker_access": worker_access,
        "page_size": page_size,
        "page_size_options": PAGE_SIZE_OPTIONS,
        "worker_list_querystring": worker_list_querystring,
        "salary_querystring": salary_querystring,
        "progress_querystring": progress_querystring,
        "snapshot_start": snapshot_start,
        "snapshot_end": today,
        "worker_snapshot": worker_snapshot,
        "summary_totals": summary_totals,
        "monthly_progress": monthly_progress,
        "active_incentive_campaigns": active_incentive_campaigns,
    }
    return render(request, "salon/salon_workers.html", context)
