from django.contrib import admin

from .models import (
    Appointment,
    BeforeAfterGallery,
    Customer,
    InventoryEntry,
    MessagingGatewayConfig,
    Offer,
    POSBill,
    POSBillItem,
    PasswordResetOTPLog,
    ProfitEntry,
    ReportBuilderSetting,
    Salon,
    SalonFeature,
    SalonFeatureImage,
    SalonPageConfig,
    SalonService,
    SalonServiceImage,
    SalonVisit,
    Testimonial,
    UserMobileProfile,
    WhatsAppCampaign,
    Worker,
    WorkerIncentiveCampaign,
    WorkerSalaryPayment,
    WebsiteSection,
)

admin.site.site_header = "Saloon Control Admin"
admin.site.site_title = "Saloon Admin"
admin.site.index_title = "Administration Portal"


class SalonFeatureInline(admin.TabularInline):
    model = SalonFeature
    extra = 1


class SalonServiceInline(admin.TabularInline):
    model = SalonService
    extra = 1


class CustomerInline(admin.TabularInline):
    model = Customer
    extra = 0
    fields = ("full_name", "phone", "whatsapp_number", "total_visits", "total_spend", "is_vip")
    readonly_fields = ("total_visits", "total_spend")


class WebsiteSectionInline(admin.TabularInline):
    model = WebsiteSection
    extra = 1


class TestimonialInline(admin.TabularInline):
    model = Testimonial
    extra = 1


class POSBillItemInline(admin.TabularInline):
    model = POSBillItem
    extra = 0
    readonly_fields = ("item_name", "quantity", "unit_price", "line_total")


@admin.register(Salon)
class SalonAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "phone", "upi_id", "is_active", "updated_at", "customer_count")
    search_fields = ("name", "owner__username", "phone", "upi_id")
    list_filter = ("is_active",)
    prepopulated_fields = {"slug": ("name",)}
    inlines = [SalonFeatureInline, SalonServiceInline, CustomerInline, WebsiteSectionInline, TestimonialInline]
    autocomplete_fields = ("owner",)
    actions = ("approve_selected_salons", "mark_selected_salons_pending")

    @admin.display(description="Customers")
    def customer_count(self, obj):
        return obj.customers.count()

    @admin.action(description="Approve selected saloons")
    def approve_selected_salons(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} saloon(s) approved and activated.")

    @admin.action(description="Mark selected saloons as pending")
    def mark_selected_salons_pending(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} saloon(s) marked pending/inactive.")


@admin.register(SalonPageConfig)
class SalonPageConfigAdmin(admin.ModelAdmin):
    list_display = ("salon", "background_style", "layout_style", "primary_color", "secondary_color")
    search_fields = ("salon__name",)


@admin.register(SalonFeature)
class SalonFeatureAdmin(admin.ModelAdmin):
    list_display = ("title", "salon", "display_order")
    search_fields = ("title", "salon__name")
    list_filter = ("salon",)


@admin.register(SalonFeatureImage)
class SalonFeatureImageAdmin(admin.ModelAdmin):
    list_display = ("feature", "display_order", "is_active", "created_at")
    search_fields = ("feature__title", "feature__salon__name")
    list_filter = ("is_active", "feature__salon")


@admin.register(SalonService)
class SalonServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "salon", "price", "duration_minutes", "is_active")
    search_fields = ("name", "salon__name", "category")
    list_filter = ("is_active", "salon")


@admin.register(SalonServiceImage)
class SalonServiceImageAdmin(admin.ModelAdmin):
    list_display = ("service", "display_order", "is_active", "created_at")
    search_fields = ("service__name", "service__salon__name")
    list_filter = ("is_active", "service__salon")


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("full_name", "salon", "phone", "total_visits", "total_spend", "last_visit", "is_vip")
    search_fields = ("full_name", "phone", "whatsapp_number", "salon__name")
    list_filter = ("salon", "is_vip")
    ordering = ("-total_spend",)


@admin.register(Offer)
class OfferAdmin(admin.ModelAdmin):
    list_display = ("title", "salon", "discount_percent", "valid_from", "valid_to", "is_active")
    search_fields = ("title", "salon__name")
    list_filter = ("is_active", "salon")


@admin.register(SalonVisit)
class SalonVisitAdmin(admin.ModelAdmin):
    list_display = ("visit_date", "salon", "customer", "service", "amount_paid", "offer")
    search_fields = ("customer__full_name", "salon__name", "service__name")
    list_filter = ("salon", "visit_date")
    date_hierarchy = "visit_date"


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("appointment_at", "salon", "customer", "customer_name", "customer_phone", "service", "status")
    search_fields = ("customer__full_name", "customer_name", "customer_phone", "salon__name", "service__name")
    list_filter = ("salon", "status", "appointment_at")
    date_hierarchy = "appointment_at"


@admin.register(WhatsAppCampaign)
class WhatsAppCampaignAdmin(admin.ModelAdmin):
    list_display = ("title", "salon", "target_filter", "sent_count", "created_at")
    search_fields = ("title", "salon__name")
    list_filter = ("salon", "target_filter")


@admin.register(WebsiteSection)
class WebsiteSectionAdmin(admin.ModelAdmin):
    list_display = ("heading", "salon", "section_type", "display_order", "is_active")
    search_fields = ("heading", "salon__name", "body")
    list_filter = ("salon", "section_type", "is_active")


@admin.register(BeforeAfterGallery)
class BeforeAfterGalleryAdmin(admin.ModelAdmin):
    list_display = ("title", "salon", "display_order", "is_active")
    search_fields = ("title", "salon__name", "description")
    list_filter = ("salon", "is_active")


@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    list_display = ("customer_name", "salon", "rating", "display_order", "is_active")
    search_fields = ("customer_name", "text", "salon__name")
    list_filter = ("salon", "rating", "is_active")


@admin.register(POSBill)
class POSBillAdmin(admin.ModelAdmin):
    list_display = ("bill_number", "salon", "customer", "bill_date", "total_amount", "payment_status")
    search_fields = ("bill_number", "salon__name", "customer__full_name")
    list_filter = ("salon", "payment_status", "payment_method")
    readonly_fields = ("bill_number", "bill_date", "subtotal", "tax_amount", "total_amount", "balance_due")
    inlines = [POSBillItemInline]


@admin.register(POSBillItem)
class POSBillItemAdmin(admin.ModelAdmin):
    list_display = ("bill", "item_name", "quantity", "unit_price", "line_total")
    search_fields = ("bill__bill_number", "item_name", "service__name")
    list_filter = ("bill__salon",)


@admin.register(ProfitEntry)
class ProfitEntryAdmin(admin.ModelAdmin):
    list_display = ("entry_date", "salon", "entry_type", "title", "amount")
    search_fields = ("title", "notes", "salon__name")
    list_filter = ("salon", "entry_type", "entry_date")


@admin.register(InventoryEntry)
class InventoryEntryAdmin(admin.ModelAdmin):
    list_display = ("purchase_date", "salon", "item_name", "quantity", "unit", "total_cost", "mark_as_expense")
    search_fields = ("item_name", "category", "notes", "salon__name")
    list_filter = ("salon", "mark_as_expense", "purchase_date")


@admin.register(ReportBuilderSetting)
class ReportBuilderSettingAdmin(admin.ModelAdmin):
    list_display = ("salon", "layout_style", "updated_at")
    search_fields = ("salon__name",)


@admin.register(Worker)
class WorkerAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "salon",
        "user",
        "can_login",
        "phone",
        "pan_number",
        "aadhaar_number",
        "is_deleted",
        "created_at",
        "payment_mode",
        "fixed_monthly_salary",
        "commission_percent",
        "is_active",
    )
    search_fields = ("full_name", "user__username", "phone", "role", "pan_number", "aadhaar_number", "city", "salon__name")
    list_filter = ("salon", "can_login", "payment_mode", "is_active", "is_deleted")
    readonly_fields = ("created_at",)
    fieldsets = (
        (
            "Worker Profile",
            {
                "fields": (
                    "salon",
                    "user",
                    "full_name",
                    "phone",
                    "role",
                    "joined_on",
                    "is_active",
                    "is_deleted",
                    "deleted_at",
                    "created_at",
                )
            },
        ),
        (
            "KYC Details",
            {
                "fields": (
                    "pan_number",
                    "aadhaar_number",
                    "address_line1",
                    "address_line2",
                    "city",
                    "state",
                    "pincode",
                )
            },
        ),
        (
            "KYC Documents (Admin Only)",
            {
                "fields": (
                    "pan_image",
                    "aadhaar_image",
                ),
                "description": "Upload/update PAN and Aadhaar document images from admin only.",
            },
        ),
        (
            "Salary & Access",
            {
                "fields": (
                    "payment_mode",
                    "fixed_monthly_salary",
                    "commission_percent",
                    "can_login",
                )
            },
        ),
    )


@admin.register(WorkerSalaryPayment)
class WorkerSalaryPaymentAdmin(admin.ModelAdmin):
    list_display = ("paid_on", "worker", "salon", "period_month", "period_year", "amount_paid")
    search_fields = ("worker__full_name", "salon__name", "notes")
    list_filter = ("salon", "period_month", "period_year")


@admin.register(WorkerIncentiveCampaign)
class WorkerIncentiveCampaignAdmin(admin.ModelAdmin):
    list_display = ("title", "salon", "bonus_percent", "valid_from", "valid_to", "is_active", "created_at")
    search_fields = ("title", "salon__name", "description")
    list_filter = ("salon", "is_active", "valid_from", "valid_to")


@admin.register(UserMobileProfile)
class UserMobileProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "mobile_number", "updated_at")
    search_fields = ("user__username", "mobile_number")


@admin.register(MessagingGatewayConfig)
class MessagingGatewayConfigAdmin(admin.ModelAdmin):
    list_display = (
        "provider",
        "is_active",
        "country_code",
        "sms_template_id",
        "whatsapp_template_id",
        "updated_at",
    )
    search_fields = ("provider", "sms_template_id", "whatsapp_template_id")
    list_filter = ("provider", "is_active")


@admin.register(PasswordResetOTPLog)
class PasswordResetOTPLogAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "username",
        "mobile_number",
        "channel",
        "otp_code",
        "provider_request_id",
        "sent_success",
        "is_verified",
        "expires_at",
        "used_at",
    )
    search_fields = ("username", "mobile_number", "otp_code")
    list_filter = ("channel", "sent_success", "is_verified", "created_at")
    readonly_fields = (
        "user",
        "username",
        "mobile_number",
        "channel",
        "otp_code",
        "provider_request_id",
        "sent_success",
        "sent_response",
        "expires_at",
        "used_at",
        "is_verified",
        "created_at",
    )
