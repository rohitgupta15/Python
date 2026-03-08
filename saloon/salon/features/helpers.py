from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone

from ..models import Salon


def get_owner_salon(request, slug):
    return get_object_or_404(Salon, slug=slug, owner=request.user)


def get_approved_owner_salon(request, slug):
    salon = get_owner_salon(request, slug)
    if not salon.is_active:
        raise PermissionDenied("This saloon is pending admin approval.")
    return salon


def target_customers_for_campaign(salon, target_filter):
    customers = salon.customers.exclude(whatsapp_number="")
    if target_filter == "vip":
        customers = customers.filter(is_vip=True)
    elif target_filter == "high_spend":
        customers = customers.filter(total_spend__gte=2000)
    elif target_filter == "inactive_60":
        cutoff = timezone.localdate() - timedelta(days=60)
        customers = customers.filter(Q(last_visit__lt=cutoff) | Q(last_visit__isnull=True))
    return customers


def generate_bill_number(salon):
    stamp = timezone.now().strftime("%Y%m%d%H%M%S")
    return f"S{salon.id}-{stamp}"


def calculate_bill_totals(bill, subtotal):
    bill.subtotal = subtotal
    bill.tax_amount = (subtotal * bill.tax_percent) / Decimal("100")
    bill.total_amount = subtotal - bill.discount_amount + bill.tax_amount
    if bill.total_amount < 0:
        bill.total_amount = Decimal("0.00")
    bill.balance_due = bill.total_amount - bill.amount_received
    if bill.balance_due <= 0:
        bill.payment_status = "paid"
        bill.balance_due = Decimal("0.00")
    elif bill.amount_received > 0:
        bill.payment_status = "partial"
    else:
        bill.payment_status = "pending"
    return bill
