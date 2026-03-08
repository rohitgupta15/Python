from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from ..forms import InventoryEntryForm
from ..models import InventoryEntry
from .helpers import get_approved_owner_salon


def _parse_month(month_key):
    if not month_key:
        return timezone.localdate().replace(day=1)
    try:
        year, month = month_key.split("-", 1)
        return timezone.datetime(int(year), int(month), 1).date()
    except (TypeError, ValueError):
        return timezone.localdate().replace(day=1)


@login_required
def salon_inventory(request, slug):
    salon = get_approved_owner_salon(request, slug)
    selected_month_date = _parse_month(request.GET.get("month"))
    selected_month = selected_month_date.strftime("%Y-%m")
    edit_id = (request.GET.get("edit_id") or "").strip()
    editing_entry = None
    if edit_id.isdigit():
        editing_entry = InventoryEntry.objects.filter(id=edit_id, salon=salon).first()

    entries_qs = salon.inventory_entries.filter(
        purchase_date__year=selected_month_date.year,
        purchase_date__month=selected_month_date.month,
    )
    if editing_entry:
        form = InventoryEntryForm(instance=editing_entry)
    else:
        form = InventoryEntryForm(initial={"purchase_date": timezone.localdate()})

    if request.method == "POST":
        form_type = request.POST.get("form_type")
        if form_type == "add_inventory":
            form = InventoryEntryForm(request.POST)
            if form.is_valid():
                entry = form.save(commit=False)
                entry.salon = salon
                entry.save()
                messages.success(request, "Inventory item added.")
                return redirect(f"{reverse('salon_inventory', kwargs={'slug': salon.slug})}?month={selected_month}")
        elif form_type == "edit_inventory":
            entry = get_object_or_404(InventoryEntry, id=request.POST.get("inventory_id"), salon=salon)
            form = InventoryEntryForm(request.POST, instance=entry)
            if form.is_valid():
                form.save()
                messages.success(request, "Inventory item updated.")
                return redirect(f"{reverse('salon_inventory', kwargs={'slug': salon.slug})}?month={selected_month}")
        elif form_type == "delete_inventory":
            entry = get_object_or_404(InventoryEntry, id=request.POST.get("inventory_id"), salon=salon)
            entry.delete()
            messages.success(request, "Inventory item deleted.")
            return redirect(f"{reverse('salon_inventory', kwargs={'slug': salon.slug})}?month={selected_month}")
        elif form_type == "toggle_inventory_expense":
            entry = get_object_or_404(InventoryEntry, id=request.POST.get("inventory_id"), salon=salon)
            entry.mark_as_expense = not entry.mark_as_expense
            entry.save(update_fields=["mark_as_expense"])
            messages.success(request, "Inventory expense flag updated.")
            return redirect(f"{reverse('salon_inventory', kwargs={'slug': salon.slug})}?month={selected_month}")

    total_cost = entries_qs.aggregate(total=Sum("total_cost")).get("total") or 0
    expense_total = entries_qs.filter(mark_as_expense=True).aggregate(total=Sum("total_cost")).get("total") or 0

    context = {
        "salon": salon,
        "form": form,
        "entries": entries_qs[:200],
        "selected_month": selected_month,
        "editing_entry": editing_entry,
        "total_cost": total_cost,
        "expense_total": expense_total,
    }
    return render(request, "salon/salon_inventory.html", context)
