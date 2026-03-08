import logging
import time
from typing import Iterable

import requests
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger(__name__)


def _get_whatsapp_config():
    token = getattr(settings, "WHATSAPP_TOKEN", "") or None
    phone_id = getattr(settings, "WHATSAPP_PHONE_ID", "") or None
    if not token or not phone_id:
        raise ImproperlyConfigured(
            "WhatsApp Cloud API credentials missing. Set WHATSAPP_TOKEN and WHATSAPP_PHONE_ID."
        )
    return token, phone_id


def _normalize_phone(phone):
    if not phone:
        return None
    digits = "".join(ch for ch in str(phone) if ch.isdigit())
    if not digits:
        return None
    default_code = getattr(settings, "WHATSAPP_DEFAULT_COUNTRY_CODE", "91").lstrip("+")
    if len(digits) <= 10:
        digits = f"{default_code}{digits}"
    return digits


def send_whatsapp_campaign_messages(customers: Iterable, message_template: str):
    """Send a simple text message through WhatsApp Cloud API for each customer."""
    token, phone_id = _get_whatsapp_config()
    api_version = getattr(settings, "WHATSAPP_API_VERSION", "v17.0")
    rate_limit = getattr(settings, "WHATSAPP_RATE_LIMIT_SECONDS", 0.5)
    timeout = getattr(settings, "WHATSAPP_TIMEOUT_SECONDS", 10.0)
    url = f"https://graph.facebook.com/{api_version}/{phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    summary = {"sent": 0, "failed": [], "skipped": []}

    for customer in customers.iterator():
        phone_raw = customer.whatsapp_number or customer.phone
        normalized = _normalize_phone(phone_raw)
        if not normalized:
            summary["skipped"].append(
                {
                    "customer_name": customer.full_name or "Customer",
                    "reason": "Missing WhatsApp-compatible phone number",
                }
            )
            continue

        personalized = f"Hi {customer.full_name or 'Customer'}, {message_template.strip()}"
        payload = {
            "messaging_product": "whatsapp",
            "to": normalized,
            "type": "text",
            "text": {"preview_url": False, "body": personalized},
        }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=timeout)
            if 200 <= response.status_code < 300:
                summary["sent"] += 1
            else:
                reason = f"{response.status_code}: {response.text}"
                summary["failed"].append(
                    {
                        "customer_name": customer.full_name or "Customer",
                        "phone": phone_raw,
                        "reason": reason,
                    }
                )
                logger.warning(
                    "WhatsApp send failed for %s (%s): %s", customer.full_name, normalized, reason
                )
        except requests.RequestException as exc:
            summary["failed"].append(
                {
                    "customer_name": customer.full_name or "Customer",
                    "phone": phone_raw,
                    "reason": str(exc),
                }
            )
            logger.warning(
                "WhatsApp send exception for %s (%s): %s", customer.full_name, normalized, exc
            )
        finally:
            if rate_limit:
                time.sleep(rate_limit)

    return summary
