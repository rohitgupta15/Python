from django.contrib import admin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("payer_name", "amount", "method", "reference", "received_at")
    search_fields = ("payer_name", "reference")
    list_filter = ("method",)

# Register your models here.
