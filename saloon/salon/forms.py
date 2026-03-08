import re
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from PIL import Image, UnidentifiedImageError
from django import forms
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.models import User

from .models import (
    Appointment,
    BeforeAfterGallery,
    Customer,
    OwnerDashboardSetting,
    TaskEntry,
    StyleConsultation,
    UserReminderPreference,
    UserMobileProfile,
    Offer,
    InventoryEntry,
    ReportBuilderSetting,
    ProfitEntry,
    Salon,
    SalonFeature,
    SalonPageConfig,
    SalonService,
    SalonVisit,
    SalonLoyaltySettings,
    Testimonial,
    POSBill,
    WhatsAppCampaign,
    WorkerIncentiveCampaign,
    Worker,
    WebsiteSection,
)
from .workers.forms import WorkerForm, WorkerSalaryPaymentForm


MAX_UPLOAD_BYTES = 5 * 1024 * 1024
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
BLOCKED_CSS_TOKENS = ("@import", "expression(", "javascript:", "<script", "</style")


def _validate_uploaded_image(upload, field_label):
    if not upload:
        return upload

    ext = Path(upload.name or "").suffix.lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise forms.ValidationError(f"{field_label} must be JPG, JPEG, PNG, or WEBP.")
    if upload.size > MAX_UPLOAD_BYTES:
        raise forms.ValidationError(f"{field_label} must be at most 5 MB.")

    try:
        Image.open(upload).verify()
    except (UnidentifiedImageError, OSError):
        raise forms.ValidationError(f"{field_label} is not a valid image file.")
    finally:
        upload.seek(0)
    return upload


COORDINATE_PATTERNS = (
    re.compile(r"@(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)"),
    re.compile(r"!3d(-?\d+(?:\.\d+)?)!4d(-?\d+(?:\.\d+)?)"),
    re.compile(r"/(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)(?:[/,]|$)"),
)


def _coordinates_from_map_url(url):
    parsed = urlparse(url)
    candidates = []

    for regex in COORDINATE_PATTERNS:
        match = regex.search(url)
        if match:
            candidates.append((match.group(1), match.group(2)))

    query = parse_qs(parsed.query)
    for key in ("q", "query", "ll", "center"):
        value = (query.get(key) or [""])[0]
        if value and "," in value:
            lat_raw, lng_raw = value.split(",", 1)
            candidates.append((lat_raw.strip(), lng_raw.strip()))

    for lat_raw, lng_raw in candidates:
        try:
            lat = Decimal(lat_raw)
            lng = Decimal(lng_raw)
        except (ArithmeticError, ValueError):
            continue
        if -90 <= lat <= 90 and -180 <= lng <= 180:
            return lat, lng
    return None, None


class RegisterForm(forms.ModelForm):
    mobile_number = forms.CharField(max_length=10)
    password = forms.CharField(widget=forms.PasswordInput)
    confirm_password = forms.CharField(widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ["username", "email", "password"]

    def clean_mobile_number(self):
        mobile_number = (self.cleaned_data.get("mobile_number") or "").strip()
        if not mobile_number.isdigit() or len(mobile_number) != 10:
            raise forms.ValidationError("Mobile number must be 10 digits.")
        if UserMobileProfile.objects.filter(mobile_number=mobile_number).exists():
            raise forms.ValidationError("This mobile number is already registered.")
        return mobile_number

    def clean_password(self):
        password = self.cleaned_data.get("password") or ""
        user = User(
            username=(self.cleaned_data.get("username") or "").strip(),
            email=(self.cleaned_data.get("email") or "").strip(),
        )
        validate_password(password, user=user)
        return password

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("password") != cleaned.get("confirm_password"):
            raise forms.ValidationError("Passwords do not match.")
        return cleaned


class SalonForm(forms.ModelForm):
    class Meta:
        model = Salon
        fields = [
            "name",
            "tagline",
            "description",
            "address",
            "phone",
            "email",
            "upi_id",
            "upi_payee_name",
            "opening_hours",
            "location_map_url",
            "latitude",
            "longitude",
            "logo",
            "cover_image",
        ]

    def clean_logo(self):
        return _validate_uploaded_image(self.cleaned_data.get("logo"), "Logo")

    def clean_cover_image(self):
        return _validate_uploaded_image(self.cleaned_data.get("cover_image"), "Cover image")

    def clean_latitude(self):
        latitude = self.cleaned_data.get("latitude")
        if latitude is not None and (latitude < -90 or latitude > 90):
            raise forms.ValidationError("Latitude must be between -90 and 90.")
        return latitude

    def clean_longitude(self):
        longitude = self.cleaned_data.get("longitude")
        if longitude is not None and (longitude < -180 or longitude > 180):
            raise forms.ValidationError("Longitude must be between -180 and 180.")
        return longitude

    def clean_location_map_url(self):
        location_map_url = (self.cleaned_data.get("location_map_url") or "").strip()
        if not location_map_url:
            return ""
        parsed = urlparse(location_map_url)
        if parsed.scheme.lower() not in {"http", "https"}:
            raise forms.ValidationError("Map URL must start with http:// or https://.")
        return location_map_url

    def clean(self):
        cleaned = super().clean()
        location_map_url = cleaned.get("location_map_url") or ""
        latitude = cleaned.get("latitude")
        longitude = cleaned.get("longitude")
        if location_map_url and (latitude is None or longitude is None):
            parsed_lat, parsed_lng = _coordinates_from_map_url(location_map_url)
            if parsed_lat is not None and parsed_lng is not None:
                cleaned["latitude"] = parsed_lat
                cleaned["longitude"] = parsed_lng
            elif latitude is None or longitude is None:
                self.add_error(
                    "location_map_url",
                    "Could not read coordinates from this link. Paste a map share link with coordinates or fill latitude/longitude.",
                )
        return cleaned


class SalonPageConfigForm(forms.ModelForm):
    class Meta:
        model = SalonPageConfig
        fields = [
            "hero_title",
            "hero_subtitle",
            "cta_text",
            "cta_link",
            "primary_color",
            "secondary_color",
            "background_style",
            "layout_style",
            "theme_preset",
            "custom_font",
            "dashboard_theme",
            "sidebar_variant",
            "owner_background",
            "visual_intensity",
            "accent_color",
            "show_feature_icons",
            "website_bg_color",
            "website_wallpaper",
            "custom_css",
        ]

    def clean_cta_link(self):
        cta_link = (self.cleaned_data.get("cta_link") or "").strip()
        if not cta_link:
            return cta_link
        parsed = urlparse(cta_link)
        if parsed.scheme.lower() != "https":
            raise forms.ValidationError("CTA link must use HTTPS.")
        return cta_link

    def clean_primary_color(self):
        value = (self.cleaned_data.get("primary_color") or "").strip()
        if value and not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
            raise forms.ValidationError("Primary color must be a valid hex color (example: #d97706).")
        return value

    def clean_secondary_color(self):
        value = (self.cleaned_data.get("secondary_color") or "").strip()
        if value and not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
            raise forms.ValidationError("Secondary color must be a valid hex color (example: #1f2937).")
        return value

    def clean_custom_css(self):
        custom_css = (self.cleaned_data.get("custom_css") or "").strip()
        if len(custom_css) > 4000:
            raise forms.ValidationError("Custom CSS is too long (max 4000 characters).")
        lowered = custom_css.lower()
        if any(token in lowered for token in BLOCKED_CSS_TOKENS):
            raise forms.ValidationError("Custom CSS contains blocked content.")
        return custom_css

    def clean_accent_color(self):
        value = (self.cleaned_data.get("accent_color") or "").strip()
        if value and not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
            raise forms.ValidationError("Accent color must be a valid hex color.")
        return value

    def clean_visual_intensity(self):
        value = self.cleaned_data.get("visual_intensity")
        if value is None:
            return 70
        if value < 0 or value > 100:
            raise forms.ValidationError("Visual intensity must be between 0 and 100.")
        return value

    def clean_website_bg_color(self):
        value = (self.cleaned_data.get("website_bg_color") or "").strip()
        if value and not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
            raise forms.ValidationError("Website background color must be a valid hex color.")
        return value

    def clean_website_wallpaper(self):
        return _validate_uploaded_image(self.cleaned_data.get("website_wallpaper"), "Website wallpaper")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["visual_intensity"].widget.attrs.update({"type": "range", "min": 0, "max": 100})


class OwnerDashboardSettingForm(forms.ModelForm):
    class Meta:
        model = OwnerDashboardSetting
        fields = ["layout_style", "show_pivot", "show_histogram", "show_pie", "show_leaderboard"]


class ReportBuilderSettingForm(forms.ModelForm):
    class Meta:
        model = ReportBuilderSetting
        fields = [
            "layout_style",
            "show_metrics_summary",
            "show_entry_forms",
            "show_profit_entries",
            "show_inventory_list",
            "show_monthly_inventory",
            "show_sales_bills",
            "show_kpi_strip",
            "show_sales_expense_chart",
            "show_expense_donut",
            "show_collections_donut",
            "show_mini_cards",
            "show_metric_customers",
            "show_metric_profit",
            "show_metric_loss",
            "show_metric_expense",
            "show_metric_workers",
            "show_metric_inventory",
        ]


class TaskEntryForm(forms.ModelForm):
    class Meta:
        model = TaskEntry
        fields = ["title", "details", "priority", "due_at", "remind_before_minutes", "popup_enabled"]
        widgets = {
            "due_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }


class UserReminderPreferenceForm(forms.ModelForm):
    class Meta:
        model = UserReminderPreference
        fields = ["popup_enabled", "popup_interval_minutes", "only_due_today"]


class StyleConsultationForm(forms.ModelForm):
    class Meta:
        model = StyleConsultation
        fields = [
            "customer_name",
            "gender",
            "face_shape",
            "hair_texture",
            "hair_length",
            "skin_type",
            "beard_preference",
            "concern_notes",
            "reference_image",
        ]

    def clean_reference_image(self):
        return _validate_uploaded_image(self.cleaned_data.get("reference_image"), "Reference image")


class SalonFeatureForm(forms.ModelForm):
    class Meta:
        model = SalonFeature
        fields = ["title", "description", "icon", "image", "display_order"]

    def clean_image(self):
        return _validate_uploaded_image(self.cleaned_data.get("image"), "Feature image")


class SalonServiceForm(forms.ModelForm):
    class Meta:
        model = SalonService
        fields = [
            "name",
            "category",
            "description",
            "image",
            "duration_minutes",
            "price",
            "is_active",
            "display_order",
        ]

    def clean_image(self):
        return _validate_uploaded_image(self.cleaned_data.get("image"), "Service image")


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = [
            "full_name",
            "phone",
            "whatsapp_number",
            "email",
            "date_of_birth",
            "referred_by",
            "is_vip",
            "notes",
        ]
        widgets = {
            "date_of_birth": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        self.salon = kwargs.pop("salon", None)
        super().__init__(*args, **kwargs)
        self.fields["referred_by"].required = False
        if self.salon:
            self.fields["referred_by"].queryset = Customer.objects.filter(salon=self.salon).order_by("full_name")

    def clean_phone(self):
        phone = (self.cleaned_data.get("phone") or "").strip()
        return phone

    def clean(self):
        cleaned = super().clean()
        phone = cleaned.get("phone")
        if self.salon and phone:
            exists = Customer.objects.filter(salon=self.salon, phone=phone)
            if self.instance.pk:
                exists = exists.exclude(pk=self.instance.pk)
            if exists.exists():
                self.add_error("phone", "This phone number already exists for this saloon.")
        referred_by = cleaned.get("referred_by")
        if referred_by and self.salon and referred_by.salon_id != self.salon.id:
            self.add_error("referred_by", "Referral customer must belong to this salon.")
        return cleaned


class OfferForm(forms.ModelForm):
    class Meta:
        model = Offer
        fields = ["title", "description", "discount_percent", "valid_from", "valid_to", "is_active"]
        widgets = {
            "valid_from": forms.DateInput(attrs={"type": "date"}),
            "valid_to": forms.DateInput(attrs={"type": "date"}),
        }


class SalonVisitForm(forms.ModelForm):
    points_to_redeem = forms.IntegerField(
        required=False,
        min_value=0,
        initial=0,
        help_text="Redeem loyalty points to reduce visit amount.",
    )
    services = forms.ModelMultipleChoiceField(
        queryset=SalonService.objects.none(),
        required=True,
        widget=forms.SelectMultiple(attrs={"size": "6"}),
        help_text="Select one or more services.",
    )

    class Meta:
        model = SalonVisit
        fields = [
            "customer",
            "services",
            "offer",
            "points_to_redeem",
            "assigned_worker",
            "visit_date",
            "amount_paid",
            "notes",
        ]
        widgets = {
            "visit_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        salon = kwargs.pop("salon", None)
        super().__init__(*args, **kwargs)
        self.salon = salon
        redeem_value = Decimal("0.25")
        min_points = 100
        if salon is not None:
            self.fields["customer"].queryset = Customer.objects.filter(salon=salon).order_by("full_name")
            self.fields["customer"].label_from_instance = (
                lambda customer: f"{customer.full_name} ({customer.phone or 'No mobile'})"
            )
            service_qs = SalonService.objects.filter(salon=salon, is_active=True).order_by("name")
            self.fields["services"].queryset = service_qs
            self.fields["services"].label_from_instance = lambda service: f"{service.name} - Rs {service.price}"
            self.fields["offer"].queryset = Offer.objects.filter(salon=salon, is_active=True).order_by("-valid_from")
            self.fields["assigned_worker"].queryset = Worker.objects.filter(
                salon=salon, is_active=True, is_deleted=False
            ).order_by("full_name")
            try:
                loyalty_settings = SalonLoyaltySettings.objects.get(salon=salon)
                redeem_value = loyalty_settings.points_redeem_value
                min_points = loyalty_settings.min_points_to_redeem
            except SalonLoyaltySettings.DoesNotExist:
                pass
        if self.instance.pk:
            selected_service_ids = list(self.instance.services.values_list("id", flat=True))
            if not selected_service_ids and self.instance.service_id:
                selected_service_ids = [self.instance.service_id]
            if selected_service_ids:
                self.initial.setdefault("services", selected_service_ids)
        self.fields["customer"].widget = forms.HiddenInput()
        self.fields["amount_paid"].widget.attrs.update({"readonly": "readonly"})
        self.fields["amount_paid"].help_text = "Amount is auto-calculated from selected services and offer."
        self.fields["points_to_redeem"].widget.attrs.update(
            {
                "data-min-points": str(min_points),
                "data-redeem-value": str(redeem_value),
            }
        )
        self.fields["points_to_redeem"].help_text = (
            f"Minimum {min_points} points. 1 point = Rs {redeem_value} discount."
        )
        self.fields["assigned_worker"].required = True

    def clean_services(self):
        services = self.cleaned_data.get("services")
        if not services:
            raise forms.ValidationError("Select at least one service.")
        return services

    def clean(self):
        cleaned = super().clean()
        services = cleaned.get("services") or []
        customer = cleaned.get("customer")
        points_to_redeem = cleaned.get("points_to_redeem") or 0
        subtotal = sum((service.price for service in services), Decimal("0.00"))
        offer = cleaned.get("offer")
        discount_percent = Decimal(str(getattr(offer, "discount_percent", 0) or 0))
        discount_value = (subtotal * discount_percent / Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        points_discount = Decimal("0.00")
        redeem_value = Decimal("0.25")
        min_points = 100
        if self.salon is not None:
            try:
                loyalty_settings = SalonLoyaltySettings.objects.get(salon=self.salon)
                redeem_value = loyalty_settings.points_redeem_value
                min_points = loyalty_settings.min_points_to_redeem
            except SalonLoyaltySettings.DoesNotExist:
                pass
        if points_to_redeem:
            if not customer:
                raise forms.ValidationError("Select customer to redeem points.")
            if points_to_redeem < min_points:
                self.add_error("points_to_redeem", f"Minimum {min_points} points required for redemption.")
            if points_to_redeem > (customer.loyalty_points or 0):
                self.add_error("points_to_redeem", "Customer has insufficient loyalty points.")
            points_discount = (Decimal(str(points_to_redeem)) * redeem_value).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            payable_before_points = (subtotal - discount_value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if points_discount > payable_before_points:
                self.add_error(
                    "points_to_redeem",
                    "Redeemed points exceed payable amount. Reduce points to continue.",
                )
        total = (subtotal - discount_value - points_discount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if total < Decimal("0.00"):
            total = Decimal("0.00")
        cleaned["amount_paid"] = total
        cleaned["points_discount"] = points_discount
        return cleaned

    def save(self, commit=True):
        visit = super().save(commit=False)
        services = list(self.cleaned_data.get("services") or [])
        visit.service = services[0] if services else None
        visit.amount_paid = self.cleaned_data.get("amount_paid") or Decimal("0.00")
        visit.points_redeemed = self.cleaned_data.get("points_to_redeem") or 0
        visit.points_discount = self.cleaned_data.get("points_discount") or Decimal("0.00")
        if commit:
            visit.save()
            self.save_m2m()
        return visit


class WhatsAppCampaignForm(forms.ModelForm):
    class Meta:
        model = WhatsAppCampaign
        fields = ["title", "offer", "target_filter", "message"]

    def __init__(self, *args, **kwargs):
        salon = kwargs.pop("salon", None)
        super().__init__(*args, **kwargs)
        if salon is not None:
            self.fields["offer"].queryset = Offer.objects.filter(salon=salon, is_active=True).order_by("-valid_from")


class WorkerIncentiveCampaignForm(forms.ModelForm):
    class Meta:
        model = WorkerIncentiveCampaign
        fields = ["title", "description", "bonus_percent", "valid_from", "valid_to", "is_active"]
        widgets = {
            "valid_from": forms.DateInput(attrs={"type": "date"}),
            "valid_to": forms.DateInput(attrs={"type": "date"}),
        }

    def clean_bonus_percent(self):
        bonus = self.cleaned_data.get("bonus_percent") or 0
        if bonus <= 0 or bonus > 100:
            raise forms.ValidationError("Incentive percent must be between 0 and 100.")
        return bonus

    def clean(self):
        cleaned = super().clean()
        valid_from = cleaned.get("valid_from")
        valid_to = cleaned.get("valid_to")
        if valid_from and valid_to and valid_to < valid_from:
            self.add_error("valid_to", "End date must be on or after start date.")
        return cleaned


class WebsiteSectionForm(forms.ModelForm):
    class Meta:
        model = WebsiteSection
        fields = ["section_type", "heading", "body", "display_order", "is_active"]


class BeforeAfterGalleryForm(forms.ModelForm):
    class Meta:
        model = BeforeAfterGallery
        fields = ["title", "before_image", "after_image", "description", "display_order", "is_active"]

    def clean_before_image(self):
        return _validate_uploaded_image(self.cleaned_data.get("before_image"), "Before image")

    def clean_after_image(self):
        return _validate_uploaded_image(self.cleaned_data.get("after_image"), "After image")


class TestimonialForm(forms.ModelForm):
    class Meta:
        model = Testimonial
        fields = ["customer_name", "text", "rating", "display_order", "is_active"]


class POSBillForm(forms.ModelForm):
    points_to_redeem = forms.IntegerField(
        required=False,
        initial=0,
        min_value=0,
        help_text="Points to redeem for discount",
    )
    birthday_coupon_code = forms.CharField(
        required=False,
        max_length=40,
        help_text="Optional birthday coupon code",
    )
    
    class Meta:
        model = POSBill
        fields = ["customer", "payment_method", "discount_amount", "tax_percent", "amount_received", "notes"]

    def __init__(self, *args, **kwargs):
        salon = kwargs.pop("salon", None)
        super().__init__(*args, **kwargs)
        if salon is not None:
            self.fields["customer"].queryset = Customer.objects.filter(salon=salon).order_by("full_name")
            self.fields["customer"].required = False
            self.fields["customer"].label_from_instance = lambda c: f"{c.full_name} ({c.loyalty_points} pts)"
        self.fields["customer"].widget = forms.HiddenInput()


class AppointmentForm(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = [
            "customer",
            "service",
            "customer_name",
            "customer_phone",
            "appointment_at",
            "status",
            "notes",
        ]
        widgets = {
            "appointment_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def __init__(self, *args, **kwargs):
        salon = kwargs.pop("salon", None)
        super().__init__(*args, **kwargs)
        if salon is not None:
            self.fields["customer"].queryset = Customer.objects.filter(salon=salon).order_by("full_name")
            self.fields["service"].queryset = SalonService.objects.filter(salon=salon, is_active=True).order_by("name")
        self.fields["customer"].required = False
        self.fields["service"].required = False

    def clean(self):
        cleaned = super().clean()
        customer = cleaned.get("customer")
        customer_name = (cleaned.get("customer_name") or "").strip()
        customer_phone = (cleaned.get("customer_phone") or "").strip()
        if not customer and not customer_name:
            raise forms.ValidationError("Select an existing customer or enter customer name for pre-booking.")
        if customer_name and not customer_phone and not customer:
            raise forms.ValidationError("Please provide customer phone for manual pre-booking.")
        cleaned["customer_name"] = customer_name
        cleaned["customer_phone"] = customer_phone
        return cleaned


class ProfitEntryForm(forms.ModelForm):
    class Meta:
        model = ProfitEntry
        fields = ["entry_date", "entry_type", "title", "amount", "notes"]
        widgets = {
            "entry_date": forms.DateInput(attrs={"type": "date"}),
        }


class InventoryEntryForm(forms.ModelForm):
    class Meta:
        model = InventoryEntry
        fields = [
            "item_name",
            "category",
            "quantity",
            "unit",
            "unit_cost",
            "purchase_date",
            "mark_as_expense",
            "notes",
        ]
        widgets = {
            "purchase_date": forms.DateInput(attrs={"type": "date"}),
        }


class PasswordResetOTPRequestForm(forms.Form):
    CHANNEL_CHOICES = [
        ("sms", "SMS"),
        ("whatsapp", "WhatsApp"),
    ]

    username = forms.CharField(max_length=150)
    channel = forms.ChoiceField(choices=CHANNEL_CHOICES, initial="sms")


class PasswordResetOTPVerifyForm(forms.Form):
    username = forms.CharField(max_length=150)
    otp = forms.CharField(max_length=6, min_length=4)
    new_password = forms.CharField(widget=forms.PasswordInput)
    confirm_password = forms.CharField(widget=forms.PasswordInput)

    def clean(self):
        cleaned = super().clean()
        pwd = cleaned.get("new_password") or ""
        confirm = cleaned.get("confirm_password") or ""
        if pwd and confirm and pwd != confirm:
            self.add_error("confirm_password", "Passwords do not match.")
        return cleaned
