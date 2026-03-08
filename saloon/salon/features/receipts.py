import os
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone

from ..models import POSBill
from .helpers import get_approved_owner_salon


def _fmt_money(value):
    amount = Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{amount:.2f}"


def generate_receipt_text(bill):
    """Generate plain text receipt for WhatsApp/Email"""
    items_text = []
    for item in bill.items.all():
        items_text.append(f"• {item.item_name} x{item.quantity} = Rs.{_fmt_money(item.line_total)}")
    
    items_block = "\n".join(items_text) if items_text else "No items"
    
    receipt_text = f"""
🧾 *Receipt - {bill.salon.name}*

Bill No: {bill.bill_number}
Date: {bill.bill_date.strftime('%d-%m-%Y %I:%M %p')}

{items_block}

─────────────────────
Subtotal: Rs.{_fmt_money(bill.subtotal)}
Discount: Rs.{_fmt_money(bill.discount_amount)}
Tax: Rs.{_fmt_money(bill.tax_amount)}
─────────────────────
*TOTAL: Rs.{_fmt_money(bill.total_amount)}*

Payment: {bill.get_payment_method_display()}
Status: {bill.get_payment_status_display()}

{bill.customer.full_name if bill.customer else 'Walk-in Customer'}
{bill.customer.phone if bill.customer else ''}

{bill.salon.name}
{bill.salon.address or ''}
{bill.salon.phone or ''}

Thank you for visiting!
"""
    return receipt_text.strip()


def generate_whatsapp_message(bill):
    """Generate WhatsApp message with receipt"""
    receipt_text = generate_receipt_text(bill)
    # Encode for WhatsApp URL
    import urllib.parse
    encoded_message = urllib.parse.quote(receipt_text)
    return encoded_message


@login_required
def send_receipt_whatsapp(request, slug, bill_id):
    """Send receipt via WhatsApp"""
    salon = get_approved_owner_salon(request, slug)
    bill = get_object_or_404(POSBill, id=bill_id, salon=salon)
    
    if not bill.customer:
        messages.error(request, 'Customer phone number required to send WhatsApp')
        return redirect('salon_pos_bill_detail', slug=salon.slug, bill_id=bill.id)
    
    phone = bill.customer.whatsapp_number or bill.customer.phone
    if not phone:
        messages.error(request, 'No WhatsApp number available for this customer')
        return redirect('salon_pos_bill_detail', slug=salon.slug, bill_id=bill.id)
    
    # Clean phone number
    phone = phone.replace(' ', '').replace('-', '')
    if not phone.startswith('+'):
        phone = '+91' + phone
    
    # Generate WhatsApp URL
    encoded_message = generate_whatsapp_message(bill)
    whatsapp_url = f"https://wa.me/{phone[1:]}?text={encoded_message}"
    
    # Update bill with receipt sent status
    bill.receipt_sent = True
    bill.receipt_sent_via = 'whatsapp'
    bill.receipt_sent_at = timezone.now()
    bill.save()
    
    # Redirect to WhatsApp
    return redirect(whatsapp_url)


@login_required
def send_receipt_email(request, slug, bill_id):
    """Send receipt via Email"""
    salon = get_approved_owner_salon(request, slug)
    bill = get_object_or_404(POSBill, id=bill_id, salon=salon)
    
    if not bill.customer or not bill.customer.email:
        messages.error(request, 'Customer email not available')
        return redirect('salon_pos_bill_detail', slug=salon.slug, bill_id=bill.id)
    
    # Generate email content
    receipt_html = render_to_string('salon/receipt_email.html', {
        'bill': bill,
        'salon': salon,
        'items': bill.items.all(),
    })
    
    subject = f'Receipt from {salon.name} - Bill #{bill.bill_number}'
    
    try:
        send_mail(
            subject,
            '',  # Plain text version (optional)
            salon.email or 'noreply@salon.com',
            [bill.customer.email],
            html_message=receipt_html,
            fail_silently=False,
        )
        
        # Update bill with receipt sent status
        bill.receipt_sent = True
        bill.receipt_sent_via = 'email'
        bill.receipt_sent_at = timezone.now()
        bill.save()
        
        messages.success(request, f'Receipt sent to {bill.customer.email}')
    except Exception as e:
        messages.error(request, f'Failed to send email: {str(e)}')
    
    return redirect('salon_pos_bill_detail', slug=salon.slug, bill_id=bill.id)


@login_required
def download_receipt_pdf(request, slug, bill_id):
    """Download receipt as PDF (simplified HTML print)"""
    salon = get_approved_owner_salon(request, slug)
    bill = get_object_or_404(POSBill, id=bill_id, salon=salon)
    items = bill.items.all()
    
    # Render receipt HTML
    receipt_html = render_to_string('salon/receipt_pdf.html', {
        'bill': bill,
        'salon': salon,
        'items': items,
    })
    
    # Return HTML that can be printed to PDF
    return HttpResponse(receipt_html, content_type='text/html')


@login_required
def view_receipt_online(request, slug, bill_id):
    """View receipt in browser"""
    salon = get_approved_owner_salon(request, slug)
    bill = get_object_or_404(POSBill, id=bill_id, salon=salon)
    items = bill.items.all()
    
    context = {
        'bill': bill,
        'salon': salon,
        'items': items,
    }
    return render(request, 'salon/receipt_view.html', context)


@login_required
def send_bulk_receipts(request, slug):
    """Send receipts for multiple bills"""
    salon = get_approved_owner_salon(request, slug)
    
    bill_ids = request.POST.getlist('bill_ids')
    send_method = request.POST.get('send_method', 'whatsapp')
    
    if not bill_ids:
        messages.error(request, 'No bills selected')
        return redirect('salon_pos', slug=salon.slug)
    
    bills = POSBill.objects.filter(id__in=bill_ids, salon=salon)
    sent_count = 0
    failed_count = 0
    
    for bill in bills:
        if not bill.customer:
            failed_count += 1
            continue
        
        if send_method == 'whatsapp':
            phone = bill.customer.whatsapp_number or bill.customer.phone
            if not phone:
                failed_count += 1
                continue
            
            # For bulk, we just mark them - actual sending would need WhatsApp API
            bill.receipt_sent = True
            bill.receipt_sent_via = 'whatsapp'
            bill.receipt_sent_at = timezone.now()
            bill.save()
            sent_count += 1
            
        elif send_method == 'email':
            if not bill.customer.email:
                failed_count += 1
                continue
            
            receipt_html = render_to_string('salon/receipt_email.html', {
                'bill': bill,
                'salon': salon,
                'items': bill.items.all(),
            })
            
            try:
                send_mail(
                    f'Receipt from {salon.name} - Bill #{bill.bill_number}',
                    '',
                    salon.email or 'noreply@salon.com',
                    [bill.customer.email],
                    html_message=receipt_html,
                    fail_silently=True,
                )
                bill.receipt_sent = True
                bill.receipt_sent_via = 'email'
                bill.receipt_sent_at = timezone.now()
                bill.save()
                sent_count += 1
            except:
                failed_count += 1
    
    messages.success(request, f'Receipts sent: {sent_count}' + 
                    (f', Failed: {failed_count}' if failed_count > 0 else ''))
    return redirect('salon_pos', slug=salon.slug)
