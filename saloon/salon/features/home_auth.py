from datetime import timedelta
from math import asin, cos, radians, sin, sqrt
from random import randint
import re
import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import Count
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from ..forms import PasswordResetOTPRequestForm, PasswordResetOTPVerifyForm, RegisterForm
from ..models import PasswordResetOTPLog, Salon, SalonFeature, UserMobileProfile, Worker
from .msg91 import send_reset_otp

MOBILE_DIGIT_RE = re.compile(r"\D+")


def _post_login_redirect(user):
    worker = Worker.objects.filter(user=user, can_login=True, is_active=True, is_deleted=False).first()
    if worker:
        return "worker_dashboard"
    return "owner_dashboard"


def _client_ip(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return (request.META.get("REMOTE_ADDR") or "unknown").strip()


def _login_cache_key(request, username):
    return f"saloon-login:{_client_ip(request)}:{(username or '').lower()}"


def _is_locked_out(cache_key):
    state = cache.get(cache_key) or {}
    lock_until = state.get("lock_until")
    if lock_until and lock_until > timezone.now():
        wait_seconds = int((lock_until - timezone.now()).total_seconds())
        return True, max(wait_seconds, 1)
    if lock_until:
        cache.delete(cache_key)
    return False, 0


def _register_login_failure(cache_key):
    max_attempts = max(int(getattr(settings, "LOGIN_MAX_ATTEMPTS", 5)), 1)
    lockout_seconds = max(int(getattr(settings, "LOGIN_LOCKOUT_SECONDS", 900)), 1)

    state = cache.get(cache_key) or {"failures": 0}
    failures = int(state.get("failures", 0)) + 1
    if failures >= max_attempts:
        lock_until = timezone.now() + timedelta(seconds=lockout_seconds)
        cache.set(cache_key, {"failures": failures, "lock_until": lock_until}, lockout_seconds)
        return True, lockout_seconds

    cache.set(cache_key, {"failures": failures}, lockout_seconds)
    return False, max_attempts - failures


def _otp_cache_key(username):
    return f"saloon-reset-otp:{(username or '').lower()}"


def _normalize_mobile_10(raw_value):
    digits = MOBILE_DIGIT_RE.sub("", str(raw_value or ""))
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    if len(digits) == 10:
        return digits
    return ""


def _resolve_or_create_mobile_profile(user):
    profile = UserMobileProfile.objects.filter(user=user).first()
    if profile and profile.mobile_number:
        normalized = _normalize_mobile_10(profile.mobile_number)
        if normalized:
            if normalized != profile.mobile_number:
                profile.mobile_number = normalized
                profile.save(update_fields=["mobile_number", "updated_at"])
            return profile

    candidate = ""
    worker = Worker.objects.filter(user=user, is_deleted=False).first()
    if worker:
        candidate = _normalize_mobile_10(worker.phone)

    if not candidate:
        owned_salon = Salon.objects.filter(owner=user).order_by("id").first()
        if owned_salon:
            candidate = _normalize_mobile_10(owned_salon.phone)

    if not candidate:
        return None

    existing = UserMobileProfile.objects.filter(mobile_number=candidate).exclude(user=user).first()
    if existing:
        return None

    if profile:
        profile.mobile_number = candidate
        profile.save(update_fields=["mobile_number", "updated_at"])
        return profile

    return UserMobileProfile.objects.create(user=user, mobile_number=candidate)


def _extract_provider_request_id(raw_response):
    try:
        payload = json.loads(raw_response or "")
    except json.JSONDecodeError:
        return ""
    for key in ("request_id", "requestId", "requestid", "message", "id"):
        value = payload.get(key)
        if value:
            return str(value).strip()[:120]
    return ""


def home(request):
    selected_feature = (request.GET.get("feature") or "").strip()
    page_size_raw = (request.GET.get("per_page") or "10").strip()
    allowed_page_sizes = {10, 20, 50}
    try:
        page_size = int(page_size_raw)
    except ValueError:
        page_size = 10
    if page_size not in allowed_page_sizes:
        page_size = 10
    page_number = (request.GET.get("page") or "1").strip()
    user_lat_raw = (request.GET.get("lat") or "").strip()
    user_lng_raw = (request.GET.get("lng") or "").strip()
    user_lat = None
    user_lng = None
    try:
        if user_lat_raw and user_lng_raw:
            user_lat = float(user_lat_raw)
            user_lng = float(user_lng_raw)
    except ValueError:
        user_lat, user_lng = None, None
    salons_qs = Salon.objects.filter(is_active=True)
    if selected_feature:
        salons_qs = salons_qs.filter(features__title__iexact=selected_feature)

    salons_qs = salons_qs.annotate(
        service_count=Count("services", distinct=True),
        feature_count=Count("features", distinct=True),
    ).distinct()
    salons = list(salons_qs)
    total_salons_count = len(salons)
    is_nearby_mode = user_lat is not None and user_lng is not None

    if is_nearby_mode:
        def distance_km(lat1, lng1, lat2, lng2):
            earth_radius = 6371.0
            d_lat = radians(lat2 - lat1)
            d_lng = radians(lng2 - lng1)
            a = (
                sin(d_lat / 2) ** 2
                + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lng / 2) ** 2
            )
            c = 2 * asin(sqrt(a))
            return earth_radius * c

        for salon in salons:
            if salon.latitude is not None and salon.longitude is not None:
                salon.distance_km = distance_km(user_lat, user_lng, float(salon.latitude), float(salon.longitude))
            else:
                salon.distance_km = None
        salons.sort(
            key=lambda s: (
                s.distance_km is None,
                s.distance_km if s.distance_km is not None else float("inf"),
                -getattr(s, "service_count", 0),
            )
        )
    else:
        for salon in salons:
            salon.distance_km = None

    paginator = Paginator(salons, page_size)
    salons_page = paginator.get_page(page_number)
    feature_options = (
        SalonFeature.objects.filter(salon__is_active=True)
        .exclude(title="")
        .values_list("title", flat=True)
        .distinct()
        .order_by("title")
    )
    return render(
        request,
        "salon/home.html",
        {
            "salons": salons_page.object_list,
            "salons_page": salons_page,
            "total_salons_count": total_salons_count,
            "page_size": page_size,
            "allowed_page_sizes": sorted(allowed_page_sizes),
            "feature_options": feature_options,
            "selected_feature": selected_feature,
            "is_nearby_mode": is_nearby_mode,
            "user_lat": user_lat_raw,
            "user_lng": user_lng_raw,
        },
    )


def register_view(request):
    if request.user.is_authenticated:
        return redirect(_post_login_redirect(request.user))
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = User.objects.create_user(
            username=form.cleaned_data["username"],
            email=form.cleaned_data["email"],
            password=form.cleaned_data["password"],
        )
        UserMobileProfile.objects.create(
            user=user,
            mobile_number=form.cleaned_data["mobile_number"],
        )
        login(request, user)
        return redirect(_post_login_redirect(user))
    return render(request, "salon/register.html", {"form": form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect(_post_login_redirect(request.user))

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "").strip()
        login_cache_key = _login_cache_key(request, username)
        is_locked, wait_seconds = _is_locked_out(login_cache_key)
        if is_locked:
            messages.error(request, f"Too many failed login attempts. Try again in {wait_seconds} seconds.")
            return render(request, "salon/login.html")

        user = authenticate(request, username=username, password=password)
        if user:
            cache.delete(login_cache_key)
            login(request, user)
            return redirect(_post_login_redirect(user))

        locked_now, detail = _register_login_failure(login_cache_key)
        if locked_now:
            messages.error(request, f"Too many failed login attempts. Try again in {detail} seconds.")
        else:
            messages.error(request, f"Invalid username or password. {detail} attempt(s) remaining.")

    return render(request, "salon/login.html")


def password_reset_otp_request(request):
    if request.user.is_authenticated:
        return redirect(_post_login_redirect(request.user))

    form = PasswordResetOTPRequestForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        username = (form.cleaned_data.get("username") or "").strip()
        channel = form.cleaned_data.get("channel") or "sms"
        user = User.objects.filter(username=username).first()
        if not user:
            messages.error(request, "Invalid username.")
            return render(request, "salon/password_reset_otp_request.html", {"form": form})

        mobile_profile = _resolve_or_create_mobile_profile(user)
        if not mobile_profile:
            messages.error(request, "No registered mobile number found for this account.")
            return render(request, "salon/password_reset_otp_request.html", {"form": form})

        otp = f"{randint(100000, 999999)}"
        sent, details = send_reset_otp(mobile_profile.mobile_number, otp, channel)
        ttl_seconds = int(getattr(settings, "SALOON_OTP_TTL_SECONDS", 300))
        provider_request_id = _extract_provider_request_id(details)
        otp_log = None
        if getattr(settings, "SALOON_OTP_LOG_ENABLED", False):
            otp_log = PasswordResetOTPLog.objects.create(
                user=user,
                username=user.username,
                mobile_number=mobile_profile.mobile_number,
                channel=channel,
                otp_code=otp,
                provider_request_id=provider_request_id,
                sent_success=sent,
                sent_response=(details or "")[:2000],
                expires_at=timezone.now() + timedelta(seconds=ttl_seconds),
            )
        if not sent:
            messages.error(request, f"Could not send OTP. {details}")
            if otp_log:
                messages.warning(request, "OTP logged in admin for testing fallback.")
            if provider_request_id and getattr(settings, "SALOON_SHOW_OTP_PROVIDER_ID", False):
                messages.info(request, f"Provider request id: {provider_request_id}")
            return render(request, "salon/password_reset_otp_request.html", {"form": form})

        cache.set(
            _otp_cache_key(username),
            {
                "otp": otp,
                "attempts": 0,
            },
            ttl_seconds,
        )
        if otp_log:
            request.session["password_reset_otp_log_id"] = otp_log.id
        request.session["password_reset_username"] = username
        request.session["password_reset_channel"] = channel
        request.session["password_reset_mobile"] = mobile_profile.mobile_number
        messages.success(request, "OTP sent successfully.")
        if provider_request_id and getattr(settings, "SALOON_SHOW_OTP_PROVIDER_ID", False):
            messages.info(request, f"Provider request id: {provider_request_id}")
        return redirect("password_reset_otp_verify")

    return render(request, "salon/password_reset_otp_request.html", {"form": form})


def password_reset_otp_verify(request):
    if request.user.is_authenticated:
        return redirect(_post_login_redirect(request.user))

    preset_username = (request.session.get("password_reset_username") or "").strip()
    initial = {"username": preset_username} if preset_username else None
    form = PasswordResetOTPVerifyForm(request.POST or None, initial=initial)

    if request.method == "POST" and form.is_valid():
        username = (form.cleaned_data.get("username") or "").strip()
        entered_otp = (form.cleaned_data.get("otp") or "").strip()
        new_password = form.cleaned_data.get("new_password") or ""

        user = User.objects.filter(username=username).first()
        if not user:
            messages.error(request, "Invalid username.")
            return render(request, "salon/password_reset_otp_verify.html", {"form": form})

        otp_state = cache.get(_otp_cache_key(username)) or {}
        stored_otp = str(otp_state.get("otp") or "")
        attempts = int(otp_state.get("attempts") or 0)
        max_attempts = int(getattr(settings, "SALOON_OTP_MAX_ATTEMPTS", 5))
        if not stored_otp:
            messages.error(request, "OTP expired or not found. Request a new OTP.")
            return redirect("password_reset_otp_request")

        if attempts >= max_attempts:
            cache.delete(_otp_cache_key(username))
            messages.error(request, "Maximum OTP attempts exceeded. Request new OTP.")
            return redirect("password_reset_otp_request")

        if entered_otp != stored_otp:
            otp_state["attempts"] = attempts + 1
            ttl = int(getattr(settings, "SALOON_OTP_TTL_SECONDS", 300))
            cache.set(_otp_cache_key(username), otp_state, ttl)
            messages.error(request, "Invalid OTP.")
            return render(request, "salon/password_reset_otp_verify.html", {"form": form})

        try:
            validate_password(new_password, user=user)
        except ValidationError as exc:
            for err in exc.messages:
                messages.error(request, err)
            return render(request, "salon/password_reset_otp_verify.html", {"form": form})

        user.set_password(new_password)
        user.save(update_fields=["password"])
        otp_log_id = request.session.get("password_reset_otp_log_id")
        if otp_log_id:
            PasswordResetOTPLog.objects.filter(id=otp_log_id).update(
                is_verified=True,
                used_at=timezone.now(),
            )
        cache.delete(_otp_cache_key(username))
        request.session.pop("password_reset_username", None)
        request.session.pop("password_reset_channel", None)
        request.session.pop("password_reset_mobile", None)
        request.session.pop("password_reset_otp_log_id", None)
        messages.success(request, "Password reset successful. Please login.")
        return redirect("login")

    return render(request, "salon/password_reset_otp_verify.html", {"form": form})


@require_POST
def logout_view(request):
    logout(request)
    return redirect("home")
