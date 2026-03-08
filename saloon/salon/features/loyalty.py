from decimal import Decimal
from datetime import timedelta
from uuid import uuid4

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import models, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from ..models import (
    BirthdayCoupon,
    Customer,
    LoyaltyPointsTransaction,
    POSBill,
    SalonLoyaltySettings,
)
from .helpers import get_approved_owner_salon


@login_required
def salon_loyalty_dashboard(request, slug):
    """Loyalty program dashboard for salon owners"""
    salon = get_approved_owner_salon(request, slug)
    
    # Get or create loyalty settings
    loyalty_settings, created = SalonLoyaltySettings.objects.get_or_create(
        salon=salon,
        defaults={
            'points_per_rupee': Decimal('1'),
            'points_redeem_value': Decimal('0.25'),
            'min_points_to_redeem': 100,
        }
    )

    if request.method == "POST":
        form_type = (request.POST.get("form_type") or "").strip()
        if form_type == "issue_birthday_coupons":
            issued_count = issue_monthly_birthday_coupons(salon, loyalty_settings)
            messages.success(request, f"Issued {issued_count} birthday coupon(s).")
            return redirect("salon_loyalty", slug=salon.slug)
    
    # Get top customers by loyalty points
    top_customers_qs = salon.customers.filter(loyalty_points__gt=0).order_by("-loyalty_points")
    top_customers_page = request.GET.get("top_customers_page")
    top_customers = Paginator(top_customers_qs, 10).get_page(top_customers_page)

    # Get recent transactions
    recent_transactions_qs = (
        LoyaltyPointsTransaction.objects.filter(salon=salon)
        .select_related("customer")
        .order_by("-created_at")
    )
    recent_transactions_page = request.GET.get("transactions_page")
    recent_transactions = Paginator(recent_transactions_qs, 10).get_page(recent_transactions_page)

    active_coupons = BirthdayCoupon.objects.filter(
        salon=salon, is_redeemed=False, valid_to__gte=timezone.localdate()
    ).select_related("customer")[:20]
    
    # Stats
    total_points_outstanding = salon.customers.aggregate(
        total=models.Sum('loyalty_points')
    )['total'] or 0
    
    total_lifetime_points = salon.customers.aggregate(
        total=models.Sum('lifetime_points')
    )['total'] or 0

    referral_credits_outstanding = salon.customers.aggregate(
        total=models.Sum('referral_credits')
    )['total'] or 0

    tier_summary = {
        "bronze": salon.customers.filter(membership_tier="bronze").count(),
        "silver": salon.customers.filter(membership_tier="silver").count(),
        "gold": salon.customers.filter(membership_tier="gold").count(),
        "platinum": salon.customers.filter(membership_tier="platinum").count(),
    }
    top_referrers = salon.customers.filter(referral_credits__gt=0).order_by("-referral_credits", "-total_visits")[:10]

    top_customers_query = request.GET.copy()
    top_customers_query.pop("top_customers_page", None)

    transactions_query = request.GET.copy()
    transactions_query.pop("transactions_page", None)
    
    context = {
        'salon': salon,
        'loyalty_settings': loyalty_settings,
        'top_customers': top_customers,
        'recent_transactions': recent_transactions,
        'total_points_outstanding': total_points_outstanding,
        'total_lifetime_points': total_lifetime_points,
        'tier_summary': tier_summary,
        'top_referrers': top_referrers,
        'referral_credits_outstanding': referral_credits_outstanding,
        'active_coupons': active_coupons,
        "top_customers_querystring": top_customers_query.urlencode(),
        "transactions_querystring": transactions_query.urlencode(),
    }
    return render(request, 'salon/salon_loyalty.html', context)


@login_required
def salon_loyalty_settings(request, slug):
    """Update loyalty program settings"""
    salon = get_approved_owner_salon(request, slug)
    
    loyalty_settings, created = SalonLoyaltySettings.objects.get_or_create(salon=salon)
    
    if request.method == 'POST':
        loyalty_settings.points_per_rupee = Decimal(request.POST.get('points_per_rupee', '1'))
        loyalty_settings.points_redeem_value = Decimal(request.POST.get('points_redeem_value', '0.25'))
        loyalty_settings.min_points_to_redeem = int(request.POST.get('min_points_to_redeem', '100'))
        loyalty_settings.enable_membership_tiers = 'enable_membership_tiers' in request.POST
        loyalty_settings.silver_tier_min_points = int(request.POST.get('silver_tier_min_points', '500'))
        loyalty_settings.gold_tier_min_points = int(request.POST.get('gold_tier_min_points', '1500'))
        loyalty_settings.platinum_tier_min_points = int(request.POST.get('platinum_tier_min_points', '3000'))
        loyalty_settings.referral_bonus_points = int(request.POST.get('referral_bonus_points', '100'))
        loyalty_settings.birthday_coupon_discount_percent = int(request.POST.get('birthday_coupon_discount_percent', '15'))
        loyalty_settings.birthday_coupon_valid_days = int(request.POST.get('birthday_coupon_valid_days', '7'))
        loyalty_settings.is_active = 'is_active' in request.POST
        loyalty_settings.save()
        messages.success(request, 'Loyalty settings updated successfully!')
        return redirect('salon_loyalty', slug=salon.slug)
    
    context = {
        'salon': salon,
        'loyalty_settings': loyalty_settings,
    }
    return render(request, 'salon/salon_loyalty_settings.html', context)


@login_required
def customer_loyalty_detail(request, slug, customer_id):
    """View loyalty details for a specific customer"""
    salon = get_approved_owner_salon(request, slug)
    customer = get_object_or_404(Customer, id=customer_id, salon=salon)
    
    transactions = customer.loyalty_transactions.order_by('-created_at')[:50]
    
    # Calculate potential redemption value
    loyalty_settings = getattr(salon, 'loyalty_settings', None)
    if loyalty_settings:
        redeemable_value = customer.loyalty_points * float(loyalty_settings.points_redeem_value)
    else:
        redeemable_value = customer.loyalty_points * 0.25
    
    context = {
        'salon': salon,
        'customer': customer,
        'transactions': transactions,
        'redeemable_value': redeemable_value,
    }
    return render(request, 'salon/customer_loyalty_detail.html', context)


@login_required
def adjust_customer_points(request, slug, customer_id):
    """Manually adjust customer loyalty points"""
    salon = get_approved_owner_salon(request, slug)
    customer = get_object_or_404(Customer, id=customer_id, salon=salon)
    
    if request.method == 'POST':
        points = int(request.POST.get('points', 0))
        transaction_type = request.POST.get('transaction_type', 'adjusted')
        description = request.POST.get('description', '')
        
        if points <= 0:
            messages.error(request, 'Points must be greater than 0')
            return redirect('customer_loyalty_detail', slug=salon.slug, customer_id=customer.id)
        
        with transaction.atomic():
            if transaction_type in ['earned', 'adjusted']:
                customer.loyalty_points += points
                customer.lifetime_points += points
            else:
                if customer.loyalty_points < points:
                    messages.error(request, 'Insufficient points balance')
                    return redirect('customer_loyalty_detail', slug=salon.slug, customer_id=customer.id)
                customer.loyalty_points -= points
            
            customer.save()
            update_customer_membership_tier(customer)
            
            LoyaltyPointsTransaction.objects.create(
                salon=salon,
                customer=customer,
                transaction_type=transaction_type,
                points=points,
                balance_after=customer.loyalty_points,
                description=description or f'Manual {transaction_type}',
            )
        
        messages.success(request, f'Points adjusted successfully! New balance: {customer.loyalty_points}')
        return redirect('customer_loyalty_detail', slug=salon.slug, customer_id=customer.id)
    
    context = {
        'salon': salon,
        'customer': customer,
    }
    return render(request, 'salon/adjust_points.html', context)


def calculate_loyalty_points(salon, bill_amount, customer=None):
    """Calculate loyalty points earned from a bill"""
    try:
        loyalty_settings = salon.loyalty_settings
        if not loyalty_settings or not loyalty_settings.is_active:
            return 0
        
        points = int(Decimal(str(bill_amount)) * loyalty_settings.points_per_rupee)
        return points
    except SalonLoyaltySettings.DoesNotExist:
        # Default: 1 point per rupee
        return int(Decimal(str(bill_amount)))


def resolve_membership_tier(settings, lifetime_points):
    if not settings.enable_membership_tiers:
        return "bronze"
    if lifetime_points >= settings.platinum_tier_min_points:
        return "platinum"
    if lifetime_points >= settings.gold_tier_min_points:
        return "gold"
    if lifetime_points >= settings.silver_tier_min_points:
        return "silver"
    return "bronze"


def update_customer_membership_tier(customer):
    try:
        settings = customer.salon.loyalty_settings
    except SalonLoyaltySettings.DoesNotExist:
        settings = SalonLoyaltySettings.objects.create(salon=customer.salon)
    tier = resolve_membership_tier(settings, customer.lifetime_points or 0)
    if customer.membership_tier != tier:
        customer.membership_tier = tier
        customer.save(update_fields=["membership_tier"])
    return tier


def award_referral_bonus(customer):
    referrer = customer.referred_by
    if not referrer:
        return 0
    try:
        settings = customer.salon.loyalty_settings
    except SalonLoyaltySettings.DoesNotExist:
        settings = SalonLoyaltySettings.objects.create(salon=customer.salon)
    bonus = max(int(settings.referral_bonus_points or 0), 0)
    if bonus <= 0:
        return 0
    referrer.referral_credits = (referrer.referral_credits or 0) + bonus
    referrer.loyalty_points = (referrer.loyalty_points or 0) + bonus
    referrer.lifetime_points = (referrer.lifetime_points or 0) + bonus
    referrer.save(update_fields=["referral_credits", "loyalty_points", "lifetime_points"])
    update_customer_membership_tier(referrer)
    LoyaltyPointsTransaction.objects.create(
        salon=customer.salon,
        customer=referrer,
        transaction_type="earned",
        points=bonus,
        balance_after=referrer.loyalty_points,
        description=f"Referral bonus for inviting {customer.full_name}",
    )
    return bonus


def _coupon_code(customer):
    token = uuid4().hex[:6].upper()
    return f"BDAY-{customer.id}-{token}"


def issue_monthly_birthday_coupons(salon, loyalty_settings):
    today = timezone.localdate()
    customers = salon.customers.filter(
        date_of_birth__month=today.month
    ).exclude(birthday_coupon_sent_year=today.year)

    issued_count = 0
    for customer in customers:
        valid_from = today
        valid_to = today + timedelta(days=max(int(loyalty_settings.birthday_coupon_valid_days or 7), 1))
        BirthdayCoupon.objects.create(
            salon=salon,
            customer=customer,
            code=_coupon_code(customer),
            discount_percent=max(int(loyalty_settings.birthday_coupon_discount_percent or 10), 1),
            valid_from=valid_from,
            valid_to=valid_to,
        )
        customer.birthday_coupon_sent_year = today.year
        customer.save(update_fields=["birthday_coupon_sent_year"])
        issued_count += 1
    return issued_count


def calculate_points_redemption(salon, points):
    """Calculate discount value from redeemed points"""
    try:
        loyalty_settings = salon.loyalty_settings
        if not loyalty_settings:
            return Decimal('0')
        
        if points < loyalty_settings.min_points_to_redeem:
            return Decimal('0')
        
        return Decimal(str(points)) * loyalty_settings.points_redeem_value
    except SalonLoyaltySettings.DoesNotExist:
        # Default: 0.25 per point
        return Decimal(str(points)) * Decimal('0.25')


@login_required
def process_loyalty_for_bill(request, slug, bill_id):
    """Process loyalty points for a completed bill"""
    salon = get_approved_owner_salon(request, slug)
    bill = get_object_or_404(POSBill, id=bill_id, salon=salon)
    
    if not bill.customer:
        messages.error(request, 'Bill must have a customer to earn loyalty points')
        return redirect('salon_pos_bill_detail', slug=salon.slug, bill_id=bill.id)
    
    customer = bill.customer
    
    # Calculate points earned
    points_earned = calculate_loyalty_points(salon, bill.total_amount, customer)
    
    # Get points to redeem from form
    points_to_redeem = int(request.POST.get('points_to_redeem', 0))
    points_discount = Decimal('0')
    
    if points_to_redeem > 0:
        if customer.loyalty_points < points_to_redeem:
            messages.error(request, 'Insufficient loyalty points')
            return redirect('salon_pos_bill_detail', slug=salon.slug, bill_id=bill.id)
        
        points_discount = calculate_points_redemption(salon, points_to_redeem)
    
    with transaction.atomic():
        # Update bill with points info
        bill.points_earned = points_earned
        bill.points_redeemed = points_to_redeem
        bill.points_discount = points_discount
        bill.save()
        
        # Update customer points - earn
        if points_earned > 0:
            customer.loyalty_points += points_earned
            customer.lifetime_points += points_earned
            customer.save()
            update_customer_membership_tier(customer)
            
            LoyaltyPointsTransaction.objects.create(
                salon=salon,
                customer=customer,
                transaction_type='earned',
                points=points_earned,
                balance_after=customer.loyalty_points,
                bill=bill,
                description=f'Points earned from bill {bill.bill_number}',
            )
        
        # Update customer points - redeem
        if points_to_redeem > 0:
            customer.loyalty_points -= points_to_redeem
            customer.save()
            
            LoyaltyPointsTransaction.objects.create(
                salon=salon,
                customer=customer,
                transaction_type='redeemed',
                points=points_to_redeem,
                balance_after=customer.loyalty_points,
                bill=bill,
                description=f'Points redeemed for Rs.{points_discount} discount on bill {bill.bill_number}',
            )
    
    messages.success(request, f'Loyalty: +{points_earned} points earned' + 
                    (f', -{points_to_redeem} points redeemed for Rs.{points_discount}' if points_to_redeem > 0 else ''))
    return redirect('salon_pos_bill_detail', slug=salon.slug, bill_id=bill.id)


def apply_loyalty_for_visit(visit):
    """Apply loyalty earn/redeem for a saved salon visit."""
    customer = visit.customer
    salon = visit.salon
    points_to_redeem = int(visit.points_redeemed or 0)
    points_earned = int(calculate_loyalty_points(salon, visit.amount_paid, customer) or 0)

    with transaction.atomic():
        if points_to_redeem > 0 and customer.loyalty_points >= points_to_redeem:
            redeemed_desc = f"Points redeemed for visit #{visit.id}"
            already_redeemed = LoyaltyPointsTransaction.objects.filter(
                salon=salon,
                customer=customer,
                transaction_type="redeemed",
                description=redeemed_desc,
            ).exists()
            if not already_redeemed:
                customer.loyalty_points -= points_to_redeem
                LoyaltyPointsTransaction.objects.create(
                    salon=salon,
                    customer=customer,
                    transaction_type="redeemed",
                    points=points_to_redeem,
                    balance_after=customer.loyalty_points,
                    description=redeemed_desc,
                )

        if points_earned > 0:
            earned_desc = f"Points earned from visit #{visit.id}"
            already_earned = LoyaltyPointsTransaction.objects.filter(
                salon=salon,
                customer=customer,
                transaction_type="earned",
                description=earned_desc,
            ).exists()
            if not already_earned:
                customer.loyalty_points += points_earned
                customer.lifetime_points = (customer.lifetime_points or 0) + points_earned
                LoyaltyPointsTransaction.objects.create(
                    salon=salon,
                    customer=customer,
                    transaction_type="earned",
                    points=points_earned,
                    balance_after=customer.loyalty_points,
                    description=earned_desc,
                )

        customer.save()
        update_customer_membership_tier(customer)
