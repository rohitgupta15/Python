from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from ..forms import AppointmentForm
from ..models import Appointment
from .helpers import get_approved_owner_salon


@login_required
def salon_appointments(request, slug):
    salon = get_approved_owner_salon(request, slug)
    form = AppointmentForm(request.POST or None, salon=salon)

    if request.method == "POST":
        form_type = request.POST.get("form_type")
        if form_type == "add_appointment" and form.is_valid():
            appointment = form.save(commit=False)
            appointment.salon = salon
            appointment.save()
            messages.success(request, "Appointment pre-booked successfully.")
            return redirect("salon_appointments", slug=salon.slug)
        if form_type == "update_status":
            appointment = get_object_or_404(Appointment, id=request.POST.get("appointment_id"), salon=salon)
            status = request.POST.get("status", "").strip()
            valid_statuses = {choice[0] for choice in Appointment.STATUS_CHOICES}
            if status in valid_statuses:
                appointment.status = status
                appointment.save(update_fields=["status"])
                messages.success(request, "Appointment status updated.")
            return redirect("salon_appointments", slug=salon.slug)
        if form_type == "delete_appointment":
            appointment = get_object_or_404(Appointment, id=request.POST.get("appointment_id"), salon=salon)
            appointment.delete()
            messages.success(request, "Appointment deleted.")
            return redirect("salon_appointments", slug=salon.slug)

    today = timezone.localdate()
    appointments = salon.appointments.select_related("customer", "service")
    upcoming_qs = appointments.filter(appointment_at__date__gte=today).order_by("appointment_at")
    recent_qs = appointments.filter(appointment_at__date__lt=today).order_by("-appointment_at")

    upcoming_page = request.GET.get("upcoming_page")
    recent_page = request.GET.get("past_page")

    upcoming = Paginator(upcoming_qs, 10).get_page(upcoming_page)
    recent = Paginator(recent_qs, 10).get_page(recent_page)

    upcoming_page_query = request.GET.copy()
    upcoming_page_query.pop("upcoming_page", None)

    recent_page_query = request.GET.copy()
    recent_page_query.pop("past_page", None)

    context = {
        "salon": salon,
        "form": form,
        "upcoming": upcoming,
        "recent": recent,
        "status_choices": Appointment.STATUS_CHOICES,
        "upcoming_page_querystring": upcoming_page_query.urlencode(),
        "past_page_querystring": recent_page_query.urlencode(),
    }
    return render(request, "salon/salon_appointments.html", context)
