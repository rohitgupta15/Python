import json
from urllib import error, request as urlrequest

from django.conf import settings
from django.db.utils import OperationalError, ProgrammingError

from ..models import MessagingGatewayConfig


def _config_values():
    auth_key = (getattr(settings, "MSG91_AUTH_KEY", "") or "").strip()
    sms_template_id = (getattr(settings, "MSG91_SMS_TEMPLATE_ID", "") or "").strip()
    whatsapp_template_id = (getattr(settings, "MSG91_WHATSAPP_TEMPLATE_ID", "") or "").strip()
    country_code = str(getattr(settings, "MSG91_COUNTRY_CODE", "91")).strip().lstrip("+")
    timeout_seconds = float(getattr(settings, "MSG91_TIMEOUT_SECONDS", 10))

    try:
        config = (
            MessagingGatewayConfig.objects.filter(provider="msg91", is_active=True)
            .order_by("-updated_at")
            .first()
        )
    except (OperationalError, ProgrammingError):
        config = None

    if config:
        auth_key = (config.auth_key or auth_key or "").strip()
        sms_template_id = (config.sms_template_id or sms_template_id or "").strip()
        whatsapp_template_id = (config.whatsapp_template_id or whatsapp_template_id or "").strip()
        country_code = (config.country_code or country_code or "91").strip().lstrip("+")
        timeout_seconds = float(config.timeout_seconds or timeout_seconds or 10)

    return {
        "auth_key": auth_key,
        "sms_template_id": sms_template_id,
        "whatsapp_template_id": whatsapp_template_id,
        "country_code": country_code,
        "timeout_seconds": timeout_seconds,
    }


def _country_prefixed(mobile_number, country_code):
    return f"{country_code}{mobile_number}"


def send_reset_otp(mobile_number, otp, channel):
    cfg = _config_values()
    auth_key = cfg["auth_key"]
    if not auth_key:
        return False, "MSG91 auth key is missing."

    template_id = ""
    route = "4"
    if channel == "whatsapp":
        template_id = cfg["whatsapp_template_id"]
        route = "whatsapp"
    else:
        template_id = cfg["sms_template_id"]
        route = "4"

    if not template_id:
        return False, f"MSG91 template id missing for {channel}."

    payload = {
        "flow_id": template_id,
        "recipients": [
            {
                "mobiles": _country_prefixed(mobile_number, cfg["country_code"]),
                "VAR1": str(otp),
            }
        ],
    }
    if route == "whatsapp":
        payload["channel"] = "whatsapp"

    req = urlrequest.Request(
        "https://api.msg91.com/api/v5/flow/",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "authkey": auth_key,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlrequest.urlopen(req, timeout=float(cfg["timeout_seconds"])) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            status_code = int(getattr(resp, "status", 200))
            if not (200 <= status_code < 300):
                return False, body
            try:
                parsed = json.loads(body)
            except json.JSONDecodeError:
                return False, f"Non-JSON response from MSG91: {body[:250]}"

            response_type = str(parsed.get("type") or parsed.get("status") or "").strip().lower()
            msg = str(parsed.get("message") or parsed.get("msg") or "").strip().lower()
            request_id = parsed.get("request_id") or parsed.get("requestId") or parsed.get("requestid")
            if response_type in {"success", "ok"}:
                return True, body
            if "success" in msg and request_id:
                return True, body
            return False, body
    except error.HTTPError as exc:
        try:
            return False, exc.read().decode("utf-8", errors="replace")
        except Exception:
            return False, f"MSG91 HTTP error {exc.code}"
    except error.URLError as exc:
        return False, f"MSG91 network error: {exc.reason}"
