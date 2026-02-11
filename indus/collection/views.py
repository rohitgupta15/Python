from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render

from .forms import PaymentForm
from .models import Payment
from .utils import group_required


@login_required
def home(request):
    return render(request, 'collection/home.html')


@login_required
@group_required('Reception')
def reception(request):
    return render(request, 'collection/reception.html')


@login_required
@group_required('Reception')
def receipting(request):
    if request.method == "POST":
        form = PaymentForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("receipting")
    else:
        form = PaymentForm()

    payments = Payment.objects.all()
    total_amount = payments.aggregate(total=Sum("amount"))["total"] or 0
    return render(
        request,
        "collection/receipting.html",
        {"form": form, "payments": payments, "total_amount": total_amount},
    )


@login_required
@group_required('Reception')
def receipting_edit(request, payment_id: int):
    payment = get_object_or_404(Payment, id=payment_id)
    if request.method == "POST":
        form = PaymentForm(request.POST, instance=payment)
        if form.is_valid():
            form.save()
            return redirect("receipting")
    else:
        form = PaymentForm(instance=payment)

    return render(
        request,
        "collection/receipting_edit.html",
        {"form": form, "payment": payment},
    )


@login_required
@group_required('ACM')
def acm(request):
    return render(request, 'collection/acm.html')


@login_required
@group_required('Agency')
def agency(request):
    return render(request, 'collection/agency.html')
