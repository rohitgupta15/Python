from decimal import Decimal
from datetime import timedelta
from urllib.parse import urlencode

from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date

from ..forms import POSBillForm
from ..models import (
    BirthdayCoupon,
    Customer,
    LoyaltyPointsTransaction,
    POSBill,
    POSBillItem,
    SalonLoyaltySettings,
    SalonService,
)
from .helpers import calculate_bill_totals, generate_bill_number, get_approved_owner_salon
from .loyalty import update_customer_membership_tier
from .payments import build_upi_payment_payload


def calculate_loyalty_points(salon, bill_amount):
    """Calculate loyalty points earned from a bill"""
    try:
        loyalty_settings = SalonLoyaltySettings.objects.get(salon=salon)
        if not loyalty_settings.is_active:
            return 0
        points = int(Decimal(str(bill_amount)) * loyalty_settings.points_per_rupee)
        return points
    except SalonLoyaltySettings.DoesNotExist:
        return int(Decimal(str(bill_amount)))


def calculate_points_redemption_value(salon, points):
    """Calculate discount value from redeemed points"""
    try:
        loyalty_settings = SalonLoyaltySettings.objects.get(salon=salon)
        if points < loyalty_settings.min_points_to_redeem:
            return Decimal("0")
        return Decimal(str(points)) * loyalty_settings.points_redeem_value
    except SalonLoyaltySettings.DoesNotExist:
        return Decimal(str(points)) * Decimal("0.25")


@login_required
def salon_customer_search(request, slug):
    salon = get_approved_owner_salon(request, slug)
    query = (request.GET.get("q") or "").strip()
    if not query:
        return JsonResponse({"results": []})
    customers = (
        salon.customers.filter(
            Q(full_name__icontains=query)
            | Q(phone__icontains=query)
            | Q(whatsapp_number__icontains=query)
        )
        .order_by("full_name")
        [:15]
    )
    results = []
    for customer in customers:
        name = customer.full_name or "Customer"
        display = f"{name}"
        if customer.phone:
            display = f"{display} ({customer.phone})"
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
def salon_service_search(request, slug):
    salon = get_approved_owner_salon(request, slug)
    query = (request.GET.get("q") or "").strip()
    if not query:
        return JsonResponse({"results": []})
    services = (
        salon.services.filter(is_active=True, name__icontains=query)
        .order_by("name")
        [:15]
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
def salon_pos(request, slug):
    salon = get_approved_owner_salon(request, slug)
    form = POSBillForm(request.POST or None, salon=salon)
    services = salon.services.filter(is_active=True).order_by("name")
    date_from = (request.GET.get("date_from") or "").strip()
    date_to = (request.GET.get("date_to") or "").strip()
    preset = (request.GET.get("preset") or "").strip().lower()
    page_size_raw = (request.GET.get("page_size") or "").strip()
    page_size = 10
    if page_size_raw.isdigit() and int(page_size_raw) in {5, 10, 20}:
        page_size = int(page_size_raw)
    selected_preset = preset if preset in {"today", "week", "month"} else ""
    if selected_preset:
        today = timezone.localdate()
        if selected_preset == "today":
            start_date = today
        elif selected_preset == "week":
            start_date = today - timedelta(days=today.weekday())
        else:
            start_date = today.replace(day=1)
        date_from = start_date.isoformat()
        date_to = today.isoformat()

    if request.method == "POST" and form.is_valid():
        service_ids = request.POST.getlist("service_id")
        item_names = request.POST.getlist("item_name")
        qtys = request.POST.getlist("qty")
        prices = request.POST.getlist("price")
        
        # Get loyalty points to redeem
        points_to_redeem = int(request.POST.get("points_to_redeem") or 0)
        coupon_code = (request.POST.get("birthday_coupon_code") or "").strip().upper()

        clean_items = []
        subtotal = Decimal("0.00")
        for idx, item_name in enumerate(item_names):
            item_name = (item_name or "").strip()
            if not item_name:
                continue
            try:
                qty = int(qtys[idx] or 1)
                price = Decimal(prices[idx] or "0")
            except Exception:
                continue
            if qty <= 0 or price < 0:
                continue
            service = None
            if idx < len(service_ids) and service_ids[idx]:
                service = SalonService.objects.filter(id=service_ids[idx], salon=salon).first()
            line_total = price * qty
            clean_items.append(
                {
                    "service": service,
                    "item_name": item_name,
                    "quantity": qty,
                    "unit_price": price,
                    "line_total": line_total,
                }
            )
            subtotal += line_total

        if not clean_items:
            messages.error(request, "Add at least one valid service/item for billing.")
        else:
            customer = form.cleaned_data.get("customer")
            points_discount = Decimal("0")
            coupon_discount = Decimal("0")
            coupon_obj = None
            
            # Handle loyalty points redemption
            if customer and points_to_redeem > 0:
                if customer.loyalty_points < points_to_redeem:
                    messages.error(request, f"Insufficient loyalty points. You have {customer.loyalty_points} points.")
                    points_to_redeem = 0
                else:
                    points_discount = calculate_points_redemption_value(salon, points_to_redeem)

            if coupon_code:
                if not customer:
                    messages.error(request, "Select customer to apply birthday coupon.")
                    return redirect("salon_pos", slug=salon.slug)
                coupon_obj = BirthdayCoupon.objects.filter(
                    salon=salon,
                    customer=customer,
                    code=coupon_code,
                    is_redeemed=False,
                    valid_from__lte=timezone.localdate(),
                    valid_to__gte=timezone.localdate(),
                ).first()
                if not coupon_obj:
                    messages.error(request, "Invalid or expired birthday coupon code.")
                    return redirect("salon_pos", slug=salon.slug)
                coupon_discount = (subtotal * Decimal(coupon_obj.discount_percent) / Decimal("100")).quantize(Decimal("0.01"))
            
            with transaction.atomic():
                bill = form.save(commit=False)
                bill.salon = salon
                bill.bill_number = generate_bill_number(salon)
                bill.points_redeemed = points_to_redeem
                bill.points_discount = points_discount
                # Add points discount to form's discount_amount
                bill.discount_amount = (bill.discount_amount or Decimal("0")) + points_discount + coupon_discount
                calculate_bill_totals(bill, subtotal)
                bill.save()
                POSBillItem.objects.bulk_create(
                    [
                        POSBillItem(
                            bill=bill,
                            service=item["service"],
                            item_name=item["item_name"],
                            quantity=item["quantity"],
                            unit_price=item["unit_price"],
                            line_total=item["line_total"],
                        )
                        for item in clean_items
                    ]
                )
                
                # Process loyalty points
                if customer:
                    # Calculate points earned
                    points_earned = calculate_loyalty_points(salon, bill.total_amount)
                    bill.points_earned = points_earned
                    bill.save()
                    
                    # Deduct redeemed points
                    if points_to_redeem > 0:
                        customer.loyalty_points -= points_to_redeem
                        LoyaltyPointsTransaction.objects.create(
                            salon=salon,
                            customer=customer,
                            transaction_type='redeemed',
                            points=points_to_redeem,
                            balance_after=customer.loyalty_points,
                            bill=bill,
                            description=f'Points redeemed for Rs.{points_discount} discount on bill {bill.bill_number}',
                        )
                    
                    # Add earned points
                    if points_earned > 0:
                        customer.loyalty_points += points_earned
                        customer.lifetime_points = (customer.lifetime_points or 0) + points_earned
                        LoyaltyPointsTransaction.objects.create(
                            salon=salon,
                            customer=customer,
                            transaction_type='earned',
                            points=points_earned,
                            balance_after=customer.loyalty_points,
                            bill=bill,
                            description=f'Points earned from bill {bill.bill_number}',
                        )
                    customer.save()
                    update_customer_membership_tier(customer)

                if coupon_obj:
                    coupon_obj.is_redeemed = True
                    coupon_obj.redeemed_at = timezone.now()
                    coupon_obj.save(update_fields=["is_redeemed", "redeemed_at"])
            
            messages.success(request, f"Bill created successfully: {bill.bill_number}")
            return redirect("salon_pos_bill_detail", slug=salon.slug, bill_id=bill.id)

    recent_bills = salon.pos_bills.select_related("customer")
    start_date = parse_date(date_from) if date_from else None
    end_date = parse_date(date_to) if date_to else None
    if start_date and end_date and start_date > end_date:
        start_date, end_date = end_date, start_date
        date_from, date_to = start_date.isoformat(), end_date.isoformat()
    if start_date:
        recent_bills = recent_bills.filter(bill_date__date__gte=start_date)
    if end_date:
        recent_bills = recent_bills.filter(bill_date__date__lte=end_date)

    bill_paginator = Paginator(recent_bills, page_size)
    bills_page = bill_paginator.get_page(request.GET.get("bill_page"))
    bill_filter_query = urlencode(
        {
            "date_from": date_from,
            "date_to": date_to,
            "page_size": page_size,
        }
    )
    today_preset_query = urlencode({"preset": "today", "page_size": page_size})
    week_preset_query = urlencode({"preset": "week", "page_size": page_size})
    month_preset_query = urlencode({"preset": "month", "page_size": page_size})
    context = {
        "salon": salon,
        "form": form,
        "services": services,
        "bills_page": bills_page,
        "date_from": date_from,
        "date_to": date_to,
        "page_size": page_size,
        "selected_preset": selected_preset,
        "bill_filter_query": bill_filter_query,
        "today_preset_query": today_preset_query,
        "week_preset_query": week_preset_query,
        "month_preset_query": month_preset_query,
    }
    return render(request, "salon/salon_pos.html", context)


@login_required
def salon_pos_bill_detail(request, slug, bill_id):
    salon = get_approved_owner_salon(request, slug)
    bill = get_object_or_404(POSBill.objects.select_related("customer"), id=bill_id, salon=salon)
    items = bill.items.select_related("service")
    payment_qr = build_upi_payment_payload(salon, bill)
    return render(
        request,
        "salon/salon_pos_bill_detail.html",
        {"salon": salon, "bill": bill, "items": items, "payment_qr": payment_qr},
    )
