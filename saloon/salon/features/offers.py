from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from ..forms import OfferForm
from ..models import Offer
from .helpers import get_approved_owner_salon


@login_required
def salon_offers(request, slug):
    salon = get_approved_owner_salon(request, slug)
    form = OfferForm(request.POST or None)
    if request.method == "POST":
        form_type = request.POST.get("form_type")
        if form_type == "add_offer" and form.is_valid():
            offer = form.save(commit=False)
            offer.salon = salon
            offer.save()
            messages.success(request, "Offer added.")
            return redirect("salon_offers", slug=salon.slug)
        if form_type == "delete_offer":
            offer = get_object_or_404(Offer, id=request.POST.get("offer_id"), salon=salon)
            offer.delete()
            messages.success(request, "Offer deleted.")
            return redirect("salon_offers", slug=salon.slug)
    offers = salon.offers.all()
    return render(request, "salon/salon_offers.html", {"salon": salon, "form": form, "offers": offers})
