from urllib.parse import quote

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ImproperlyConfigured
from django.shortcuts import render

from ..forms import WhatsAppCampaignForm
from .helpers import get_approved_owner_salon, target_customers_for_campaign
from .whatsapp import send_whatsapp_campaign_messages


@login_required
def salon_whatsapp_campaign(request, slug):
    salon = get_approved_owner_salon(request, slug)
    form = WhatsAppCampaignForm(request.POST or None, salon=salon)
    preview_links = []
    bulk_status = None
    campaign = None

    if request.method == "POST" and form.is_valid():
        campaign = form.save(commit=False)
        campaign.salon = salon
        campaign.save()
        customers = target_customers_for_campaign(salon, campaign.target_filter)
        base_message = campaign.message
        if campaign.offer:
            base_message = (
                f"{campaign.message}\n\nOffer: {campaign.offer.title} ({campaign.offer.discount_percent}% off) "
                f"valid till {campaign.offer.valid_to}"
            )
        try:
            bulk_status = send_whatsapp_campaign_messages(customers, base_message)
            campaign.sent_count = bulk_status["sent"]
            campaign.save(update_fields=["sent_count"])
            messages.success(
                request,
                f"WhatsApp campaign dispatched via Cloud API to {bulk_status['sent']} customers.",
            )
            if bulk_status["failed"]:
                messages.warning(
                    request,
                    f"Failed to deliver to {len(bulk_status['failed'])} customers; see status below.",
                )
            if bulk_status["skipped"]:
                messages.info(
                    request,
                    f"Skipped {len(bulk_status['skipped'])} customers that lacked a WhatsApp number.",
                )
        except ImproperlyConfigured as exc:
            messages.warning(request, str(exc))

            def _generate_preview():
                fallback = []
                for customer in customers:
                    number = "".join(ch for ch in customer.whatsapp_number or customer.phone if ch.isdigit())
                    if not number:
                        continue
                    personalized = f"Hi {customer.full_name}, {base_message}"
                    fallback.append(
                        {
                            "customer": customer,
                            "url": f"https://wa.me/{number}?text={quote(personalized)}",
                        }
                    )
                return fallback

            preview_links = _generate_preview()

    recent_campaigns = salon.campaigns.select_related("offer")[:10]
    context = {
        "salon": salon,
        "form": form,
        "preview_links": preview_links,
        "campaign": campaign,
        "bulk_status": bulk_status,
        "recent_campaigns": recent_campaigns,
    }
    return render(request, "salon/salon_whatsapp_campaign.html", context)
