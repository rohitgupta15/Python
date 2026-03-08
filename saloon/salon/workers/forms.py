from decimal import Decimal, ROUND_HALF_UP

from django import forms

from ..models import Customer, Offer, SalonLoyaltySettings, SalonService, SalonVisit, Worker, WorkerSalaryPayment
from .validators import (
    validate_aadhaar_number,
    validate_mobile_10,
    validate_pan_number,
    validate_pincode,
)


class WorkerForm(forms.ModelForm):
    class Meta:
        model = Worker
        fields = [
            "full_name",
            "phone",
            "role",
            "pan_number",
            "aadhaar_number",
            "address_line1",
            "address_line2",
            "city",
            "state",
            "pincode",
            "payment_mode",
            "fixed_monthly_salary",
            "commission_percent",
            "is_active",
            "joined_on",
        ]
        widgets = {
            "joined_on": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["fixed_monthly_salary"].required = False
        self.fields["commission_percent"].required = False
        self.fields["phone"].widget.attrs.update(
            {
                "maxlength": "10",
                "inputmode": "numeric",
                "pattern": r"\d{10}",
                "placeholder": "10 digit mobile number",
            }
        )
        self.fields["aadhaar_number"].widget.attrs.update(
            {
                "maxlength": "12",
                "inputmode": "numeric",
                "pattern": r"\d{12}",
                "placeholder": "12 digit Aadhaar",
            }
        )
        self.fields["pan_number"].widget.attrs.update(
            {
                "maxlength": "10",
                "style": "text-transform:uppercase;",
                "placeholder": "ABCDE1234F",
            }
        )
        self.fields["pincode"].widget.attrs.update(
            {
                "maxlength": "6",
                "inputmode": "numeric",
                "pattern": r"\d{6}",
            }
        )

    def clean_phone(self):
        phone = (self.cleaned_data.get("phone") or "").strip()
        validate_mobile_10(phone)
        return phone

    def clean_pan_number(self):
        pan_number = (self.cleaned_data.get("pan_number") or "").strip().upper()
        validate_pan_number(pan_number)
        return pan_number

    def clean_aadhaar_number(self):
        aadhaar_number = (self.cleaned_data.get("aadhaar_number") or "").strip()
        validate_aadhaar_number(aadhaar_number)
        return aadhaar_number

    def clean_pincode(self):
        pincode = (self.cleaned_data.get("pincode") or "").strip()
        validate_pincode(pincode)
        return pincode

    def clean_commission_percent(self):
        value = self.cleaned_data.get("commission_percent") or 0
        if value < 0 or value > 100:
            raise forms.ValidationError("Commission must be between 0 and 100.")
        return value

    def clean(self):
        cleaned = super().clean()
        payment_mode = cleaned.get("payment_mode")
        fixed_monthly_salary = cleaned.get("fixed_monthly_salary") or 0
        commission_percent = cleaned.get("commission_percent") or 0

        pan_number = cleaned.get("pan_number")
        aadhaar_number = cleaned.get("aadhaar_number")
        if not pan_number and not aadhaar_number:
            raise forms.ValidationError("Provide at least one KYC ID: PAN or Aadhaar.")

        if not cleaned.get("address_line1"):
            self.add_error("address_line1", "Address line 1 is required for KYC.")
        if not cleaned.get("city"):
            self.add_error("city", "City is required for KYC.")
        if not cleaned.get("state"):
            self.add_error("state", "State is required for KYC.")
        if not cleaned.get("pincode"):
            self.add_error("pincode", "Pincode is required for KYC.")

        if payment_mode == "commission":
            cleaned["fixed_monthly_salary"] = 0
            if commission_percent <= 0:
                self.add_error("commission_percent", "Enter commission percentage for commission mode.")
        elif payment_mode == "fixed":
            cleaned["commission_percent"] = 0
            if fixed_monthly_salary <= 0:
                self.add_error("fixed_monthly_salary", "Enter fixed monthly salary for fixed mode.")

        return cleaned


class WorkerSalaryPaymentForm(forms.ModelForm):
    class Meta:
        model = WorkerSalaryPayment
        fields = ["worker", "period_month", "period_year", "amount_paid", "paid_on", "notes"]
        widgets = {
            "paid_on": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        salon = kwargs.pop("salon", None)
        super().__init__(*args, **kwargs)
        if salon is not None:
            self.fields["worker"].queryset = Worker.objects.filter(
                salon=salon, is_active=True, is_deleted=False
            ).order_by("full_name")

    def clean_period_month(self):
        month = self.cleaned_data.get("period_month")
        if month < 1 or month > 12:
            raise forms.ValidationError("Month must be between 1 and 12.")
        return month


class WorkerVisitForm(forms.ModelForm):
    points_to_redeem = forms.IntegerField(
        required=False,
        min_value=0,
        initial=0,
        help_text="Redeem loyalty points for this visit.",
    )
    services = forms.ModelMultipleChoiceField(
        queryset=SalonService.objects.none(),
        required=True,
        widget=forms.SelectMultiple(attrs={"size": "6"}),
        help_text="Select one or more services.",
    )

    class Meta:
        model = SalonVisit
        fields = ["customer", "services", "offer", "points_to_redeem", "visit_date", "amount_paid", "notes"]
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
            {"data-min-points": str(min_points), "data-redeem-value": str(redeem_value)}
        )
        self.fields["points_to_redeem"].help_text = (
            f"Minimum {min_points} points. 1 point = Rs {redeem_value} discount."
        )

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
