import calendar
from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from ..forms import WorkerIncentiveCampaignForm
from ..models import WorkerIncentiveCampaign
from .helpers import get_approved_owner_salon


@login_required
def salon_incentive_campaigns(request, slug):
    salon = get_approved_owner_salon(request, slug)
    selected_month = (request.GET.get("month") or datetime.now().strftime("%Y-%m")).strip()
    form = WorkerIncentiveCampaignForm(request.POST or None)

    if request.method == "POST":
        form_type = (request.POST.get("form_type") or "").strip()
        if form_type == "create_campaign":
            if form.is_valid():
                campaign = form.save(commit=False)
                campaign.salon = salon
                campaign.save()
                messages.success(request, "Incentive campaign created.")
                return redirect("salon_incentive_campaigns", slug=salon.slug)
            messages.error(request, "Please correct campaign form errors.")
        elif form_type == "toggle_campaign":
            campaign = get_object_or_404(
                WorkerIncentiveCampaign, id=request.POST.get("campaign_id"), salon=salon
            )
            campaign.is_active = not campaign.is_active
            campaign.save(update_fields=["is_active"])
            messages.success(request, f"Campaign {'activated' if campaign.is_active else 'paused'}.")
            return redirect("salon_incentive_campaigns", slug=salon.slug)
        elif form_type == "delete_campaign":
            campaign = get_object_or_404(
                WorkerIncentiveCampaign, id=request.POST.get("campaign_id"), salon=salon
            )
            campaign.delete()
            messages.success(request, "Campaign deleted.")
            return redirect("salon_incentive_campaigns", slug=salon.slug)

    campaigns_qs = salon.worker_incentive_campaigns.order_by("-created_at")
    campaign_page = request.GET.get("page") or "1"
    campaigns = Paginator(campaigns_qs, 10).get_page(campaign_page)
    campaign_query = request.GET.copy()
    campaign_query.pop("page", None)

    if selected_month:
        try:
            month_dt = datetime.strptime(selected_month, "%Y-%m")
            month_start = month_dt.date().replace(day=1)
            month_end_day = calendar.monthrange(month_dt.year, month_dt.month)[1]
            month_end = month_dt.date().replace(day=month_end_day)
        except ValueError:
            month_start = None
            month_end = None
    else:
        month_start = None
        month_end = None

    active_for_month = salon.worker_incentive_campaigns.none()
    if month_start and month_end:
        active_for_month = salon.worker_incentive_campaigns.filter(
            is_active=True,
            valid_from__lte=month_end,
            valid_to__gte=month_start,
        ).order_by("-bonus_percent", "-created_at")

    context = {
        "salon": salon,
        "form": form,
        "campaigns": campaigns,
        "campaign_querystring": campaign_query.urlencode(),
        "selected_month": selected_month,
        "active_for_month": active_for_month,
    }
    return render(request, "salon/salon_incentive_campaigns.html", context)
