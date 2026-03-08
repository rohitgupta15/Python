from django.contrib.auth import get_user_model
from django.db import models
from django.utils.text import slugify

User = get_user_model()


class Salon(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="salons")
    name = models.CharField(max_length=180)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    tagline = models.CharField(max_length=240, blank=True)
    description = models.TextField(blank=True)
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    upi_id = models.CharField(max_length=120, blank=True, help_text="Example: mysalon@okhdfcbank")
    upi_payee_name = models.CharField(max_length=120, blank=True, help_text="Name shown in UPI payment apps")
    opening_hours = models.CharField(max_length=120, blank=True)
    location_map_url = models.URLField(blank=True, help_text="Public map link for this salon location.")
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    logo = models.ImageField(upload_to="salons/logos/", blank=True, null=True)
    cover_image = models.ImageField(upload_to="salons/covers/", blank=True, null=True)
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name) or "salon"
            slug = base_slug
            index = 1
            while Salon.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                index += 1
                slug = f"{base_slug}-{index}"
            self.slug = slug
        super().save(*args, **kwargs)


class SalonPageConfig(models.Model):
    BACKGROUND_CHOICES = [
        ("warm", "Warm"),
        ("cool", "Cool"),
        ("light", "Light"),
    ]
    LAYOUT_CHOICES = [
        ("classic", "Classic"),
        ("cards", "Cards"),
        ("minimal", "Minimal"),
    ]
    THEME_CHOICES = [
        ("sunset", "Sunset"),
        ("forest", "Forest"),
        ("ocean", "Ocean"),
        ("rose", "Rose"),
    ]
    FONT_CHOICES = [
        ("poppins", "Poppins"),
        ("lora", "Lora"),
        ("montserrat", "Montserrat"),
        ("playfair", "Playfair Display"),
    ]
    DASHBOARD_THEME_CHOICES = [
        ("signature", "Signature"),
        ("luxury", "Luxury"),
        ("vibrant", "Vibrant"),
        ("minimal", "Minimal"),
    ]
    SIDEBAR_VARIANT_CHOICES = [
        ("glass", "Glass"),
        ("solid", "Solid"),
        ("minimal", "Minimal"),
    ]
    OWNER_BACKGROUND_CHOICES = [
        ("aurora", "Aurora"),
        ("mesh", "Mesh"),
        ("pearl", "Pearl"),
        ("charcoal", "Charcoal"),
    ]

    salon = models.OneToOneField(Salon, on_delete=models.CASCADE, related_name="page_config")
    hero_title = models.CharField(max_length=200, blank=True)
    hero_subtitle = models.TextField(blank=True)
    cta_text = models.CharField(max_length=60, default="Book Appointment")
    cta_link = models.URLField(blank=True)
    primary_color = models.CharField(max_length=7, default="#d97706")
    secondary_color = models.CharField(max_length=7, default="#1f2937")
    background_style = models.CharField(max_length=20, choices=BACKGROUND_CHOICES, default="warm")
    layout_style = models.CharField(max_length=20, choices=LAYOUT_CHOICES, default="classic")
    theme_preset = models.CharField(max_length=20, choices=THEME_CHOICES, default="sunset")
    custom_font = models.CharField(max_length=20, choices=FONT_CHOICES, default="poppins")
    dashboard_theme = models.CharField(max_length=20, choices=DASHBOARD_THEME_CHOICES, default="signature")
    sidebar_variant = models.CharField(max_length=20, choices=SIDEBAR_VARIANT_CHOICES, default="glass")
    owner_background = models.CharField(max_length=20, choices=OWNER_BACKGROUND_CHOICES, default="aurora")
    visual_intensity = models.PositiveIntegerField(default=70)
    accent_color = models.CharField(max_length=7, default="#0f766e")
    show_feature_icons = models.BooleanField(default=True)
    custom_css = models.TextField(blank=True)
    website_bg_color = models.CharField(max_length=7, default="#f8fafc")
    website_wallpaper = models.ImageField(upload_to="salons/wallpapers/", blank=True, null=True)

    def __str__(self):
        return f"Page config: {self.salon.name}"


class OwnerDashboardSetting(models.Model):
    LAYOUT_CHOICES = [
        ("mixed", "Mixed Dashboard"),
        ("pivot_grid", "Pivot Grid Focus"),
        ("histogram", "Histogram Focus"),
        ("pie", "Pie Focus"),
    ]

    owner = models.OneToOneField(User, on_delete=models.CASCADE, related_name="owner_dashboard_setting")
    layout_style = models.CharField(max_length=20, choices=LAYOUT_CHOICES, default="mixed")
    show_pivot = models.BooleanField(default=True)
    show_histogram = models.BooleanField(default=True)
    show_pie = models.BooleanField(default=True)
    show_leaderboard = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Owner dashboard: {self.owner.username}"


class ReportBuilderSetting(models.Model):
    LAYOUT_CHOICES = [
        ("balanced", "Balanced"),
        ("financial_focus", "Financial Focus"),
        ("inventory_focus", "Inventory Focus"),
    ]

    salon = models.OneToOneField(Salon, on_delete=models.CASCADE, related_name="report_builder_setting")
    layout_style = models.CharField(max_length=30, choices=LAYOUT_CHOICES, default="balanced")
    show_metrics_summary = models.BooleanField(default=True)
    show_entry_forms = models.BooleanField(default=True)
    show_profit_entries = models.BooleanField(default=True)
    show_inventory_list = models.BooleanField(default=True)
    show_monthly_inventory = models.BooleanField(default=True)
    show_sales_bills = models.BooleanField(default=True)
    show_kpi_strip = models.BooleanField(default=True)
    show_sales_expense_chart = models.BooleanField(default=True)
    show_expense_donut = models.BooleanField(default=True)
    show_collections_donut = models.BooleanField(default=True)
    show_mini_cards = models.BooleanField(default=True)
    show_metric_customers = models.BooleanField(default=True)
    show_metric_profit = models.BooleanField(default=True)
    show_metric_loss = models.BooleanField(default=True)
    show_metric_expense = models.BooleanField(default=True)
    show_metric_workers = models.BooleanField(default=True)
    show_metric_inventory = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Report builder: {self.salon.name}"


class UserReminderPreference(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="reminder_preference")
    popup_enabled = models.BooleanField(default=True)
    popup_interval_minutes = models.PositiveIntegerField(default=30)
    only_due_today = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Reminder preference: {self.user.username}"


class UserMobileProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="mobile_profile")
    mobile_number = models.CharField(max_length=10, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} mobile {self.mobile_number}"


class MessagingGatewayConfig(models.Model):
    provider = models.CharField(max_length=40, default="msg91", unique=True)
    auth_key = models.CharField(max_length=255, blank=True)
    sms_template_id = models.CharField(max_length=120, blank=True)
    whatsapp_template_id = models.CharField(max_length=120, blank=True)
    country_code = models.CharField(max_length=6, default="91")
    timeout_seconds = models.DecimalField(max_digits=5, decimal_places=2, default=10)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Messaging Gateway Config"
        verbose_name_plural = "Messaging Gateway Config"

    def __str__(self):
        return f"{self.provider.upper()} config"


class PasswordResetOTPLog(models.Model):
    CHANNEL_CHOICES = [
        ("sms", "SMS"),
        ("whatsapp", "WhatsApp"),
    ]

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="password_reset_otp_logs")
    username = models.CharField(max_length=150)
    mobile_number = models.CharField(max_length=10, blank=True)
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES, default="sms")
    otp_code = models.CharField(max_length=10)
    provider_request_id = models.CharField(max_length=120, blank=True)
    sent_success = models.BooleanField(default=False)
    sent_response = models.TextField(blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    used_at = models.DateTimeField(null=True, blank=True)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"OTP log {self.username} {self.channel} {self.created_at}"


class TaskEntry(models.Model):
    TASK_TYPES = [
        ("todo", "To-Do"),
        ("note", "Note"),
        ("reminder", "Reminder"),
    ]
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("completed", "Completed"),
    ]
    PRIORITY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tasks")
    salon = models.ForeignKey(Salon, on_delete=models.SET_NULL, null=True, blank=True, related_name="tasks")
    title = models.CharField(max_length=180)
    details = models.TextField(blank=True)
    task_type = models.CharField(max_length=20, choices=TASK_TYPES, default="todo")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default="medium")
    due_at = models.DateTimeField(null=True, blank=True)
    remind_before_minutes = models.PositiveIntegerField(default=30)
    popup_enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("status", "due_at", "-created_at")

    def __str__(self):
        return f"{self.title} ({self.user.username})"


class StyleConsultation(models.Model):
    GENDER_CHOICES = [
        ("male", "Male"),
        ("female", "Female"),
        ("other", "Other"),
    ]
    FACE_SHAPE_CHOICES = [
        ("oval", "Oval"),
        ("round", "Round"),
        ("square", "Square"),
        ("heart", "Heart"),
        ("diamond", "Diamond"),
        ("long", "Long"),
    ]
    HAIR_TEXTURE_CHOICES = [
        ("straight", "Straight"),
        ("wavy", "Wavy"),
        ("curly", "Curly"),
        ("coily", "Coily"),
    ]
    HAIR_LENGTH_CHOICES = [
        ("short", "Short"),
        ("medium", "Medium"),
        ("long", "Long"),
    ]
    SKIN_TYPE_CHOICES = [
        ("normal", "Normal"),
        ("dry", "Dry"),
        ("oily", "Oily"),
        ("combination", "Combination"),
        ("sensitive", "Sensitive"),
    ]
    BEARD_CHOICES = [
        ("clean", "Clean Shave"),
        ("stubble", "Stubble"),
        ("boxed", "Boxed Beard"),
        ("full", "Full Beard"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="style_consultations")
    salon = models.ForeignKey(Salon, on_delete=models.SET_NULL, null=True, blank=True, related_name="style_consultations")
    customer_name = models.CharField(max_length=140, blank=True)
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES, default="male")
    face_shape = models.CharField(max_length=20, choices=FACE_SHAPE_CHOICES, default="oval")
    hair_texture = models.CharField(max_length=20, choices=HAIR_TEXTURE_CHOICES, default="straight")
    hair_length = models.CharField(max_length=20, choices=HAIR_LENGTH_CHOICES, default="short")
    skin_type = models.CharField(max_length=20, choices=SKIN_TYPE_CHOICES, default="normal")
    beard_preference = models.CharField(max_length=20, choices=BEARD_CHOICES, default="clean")
    concern_notes = models.TextField(blank=True)
    reference_image = models.ImageField(upload_to="style_advisor/")
    transformed_preview_image = models.ImageField(upload_to="style_advisor/previews/", blank=True, null=True)
    suggested_haircut = models.CharField(max_length=160, blank=True)
    suggested_beard = models.CharField(max_length=160, blank=True)
    suggested_facial = models.CharField(max_length=160, blank=True)
    suggested_scrub = models.CharField(max_length=160, blank=True)
    selected_style = models.CharField(max_length=160, blank=True)
    suggestion_source = models.CharField(max_length=20, default="rule")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"Style consultation #{self.id} ({self.user.username})"


class SalonFeature(models.Model):
    salon = models.ForeignKey(Salon, on_delete=models.CASCADE, related_name="features")
    title = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=40, blank=True, help_text="Example: scissors")
    image = models.ImageField(upload_to="salons/features/", blank=True, null=True)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("display_order", "id")

    def __str__(self):
        return f"{self.title} ({self.salon.name})"


class SalonFeatureImage(models.Model):
    feature = models.ForeignKey(SalonFeature, on_delete=models.CASCADE, related_name="gallery_images")
    image = models.ImageField(upload_to="salons/features/gallery/")
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("display_order", "id")

    def __str__(self):
        return f"{self.feature.title} image #{self.id}"


class SalonService(models.Model):
    salon = models.ForeignKey(Salon, on_delete=models.CASCADE, related_name="services")
    name = models.CharField(max_length=150)
    category = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="salons/services/", blank=True, null=True)
    duration_minutes = models.PositiveIntegerField(default=30)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("display_order", "name")

    def __str__(self):
        return f"{self.name} ({self.salon.name})"


class SalonServiceImage(models.Model):
    service = models.ForeignKey(SalonService, on_delete=models.CASCADE, related_name="gallery_images")
    image = models.ImageField(upload_to="salons/services/gallery/")
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("display_order", "id")

    def __str__(self):
        return f"{self.service.name} image #{self.id}"


class Offer(models.Model):
    salon = models.ForeignKey(Salon, on_delete=models.CASCADE, related_name="offers")
    title = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    discount_percent = models.PositiveIntegerField(default=10)
    valid_from = models.DateField()
    valid_to = models.DateField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("-valid_from", "title")

    def __str__(self):
        return f"{self.title} ({self.salon.name})"


class Customer(models.Model):
    TIER_CHOICES = [
        ("bronze", "Bronze"),
        ("silver", "Silver"),
        ("gold", "Gold"),
        ("platinum", "Platinum"),
    ]

    salon = models.ForeignKey(Salon, on_delete=models.CASCADE, related_name="customers")
    full_name = models.CharField(max_length=160)
    phone = models.CharField(max_length=20)
    whatsapp_number = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    last_visit = models.DateField(null=True, blank=True)
    total_visits = models.PositiveIntegerField(default=0)
    total_spend = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_vip = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    # Loyalty points fields
    loyalty_points = models.PositiveIntegerField(default=0, help_text="Current loyalty points balance")
    lifetime_points = models.PositiveIntegerField(default=0, help_text="Total points earned all time")
    membership_tier = models.CharField(max_length=20, choices=TIER_CHOICES, default="bronze")
    referred_by = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="referrals"
    )
    referral_credits = models.PositiveIntegerField(default=0, help_text="Referral credits available for redemption")
    birthday_coupon_sent_year = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-total_spend", "full_name")
        unique_together = ("salon", "phone")

    def __str__(self):
        return f"{self.full_name} ({self.salon.name})"


class LoyaltyPointsTransaction(models.Model):
    """Track loyalty points earning and redemption history"""
    TRANSACTION_TYPES = [
        ("earned", "Points Earned"),
        ("redeemed", "Points Redeemed"),
        ("expired", "Points Expired"),
        ("adjusted", "Points Adjusted"),
    ]

    salon = models.ForeignKey(Salon, on_delete=models.CASCADE, related_name="loyalty_transactions")
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="loyalty_transactions")
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES, default="earned")
    points = models.PositiveIntegerField(help_text="Points added (positive) or deducted (negative)")
    balance_after = models.PositiveIntegerField(help_text="Points balance after this transaction")
    bill = models.ForeignKey("POSBill", on_delete=models.SET_NULL, null=True, blank=True, related_name="loyalty_transactions")
    description = models.CharField(max_length=250, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "Loyalty Points Transaction"
        verbose_name_plural = "Loyalty Points Transactions"

    def __str__(self):
        return f"{self.customer.full_name} - {self.get_transaction_type_display()} ({self.points} pts)"


class SalonLoyaltySettings(models.Model):
    """Store loyalty program settings per salon"""
    salon = models.OneToOneField(Salon, on_delete=models.CASCADE, related_name="loyalty_settings")
    points_per_rupee = models.DecimalField(max_digits=5, decimal_places=2, default=1, help_text="Points earned per Rs.1 spent")
    points_redeem_value = models.DecimalField(max_digits=5, decimal_places=2, default=0.25, help_text="Rs. value per point when redeemed")
    min_points_to_redeem = models.PositiveIntegerField(default=100, help_text="Minimum points required to redeem")
    enable_membership_tiers = models.BooleanField(default=True)
    silver_tier_min_points = models.PositiveIntegerField(default=500)
    gold_tier_min_points = models.PositiveIntegerField(default=1500)
    platinum_tier_min_points = models.PositiveIntegerField(default=3000)
    referral_bonus_points = models.PositiveIntegerField(default=100)
    birthday_coupon_discount_percent = models.PositiveIntegerField(default=15)
    birthday_coupon_valid_days = models.PositiveIntegerField(default=7)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Loyalty Settings - {self.salon.name}"


class BirthdayCoupon(models.Model):
    salon = models.ForeignKey(Salon, on_delete=models.CASCADE, related_name="birthday_coupons")
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="birthday_coupons")
    code = models.CharField(max_length=40, unique=True)
    discount_percent = models.PositiveIntegerField(default=10)
    valid_from = models.DateField()
    valid_to = models.DateField()
    is_redeemed = models.BooleanField(default=False)
    redeemed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.code} ({self.customer.full_name})"


class Worker(models.Model):
    PAYMENT_MODES = [
        ("fixed", "Monthly Fixed"),
        ("commission", "Commission Based"),
    ]

    salon = models.ForeignKey(Salon, on_delete=models.CASCADE, related_name="workers")
    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="worker_profile")
    full_name = models.CharField(max_length=140)
    phone = models.CharField(max_length=20, blank=True)
    role = models.CharField(max_length=100, blank=True)
    pan_number = models.CharField(max_length=10, blank=True)
    aadhaar_number = models.CharField(max_length=12, blank=True)
    pan_image = models.ImageField(upload_to="workers/kyc/pan/", blank=True, null=True)
    aadhaar_image = models.ImageField(upload_to="workers/kyc/aadhaar/", blank=True, null=True)
    address_line1 = models.CharField(max_length=180, blank=True)
    address_line2 = models.CharField(max_length=180, blank=True)
    city = models.CharField(max_length=80, blank=True)
    state = models.CharField(max_length=80, blank=True)
    pincode = models.CharField(max_length=6, blank=True)
    payment_mode = models.CharField(max_length=20, choices=PAYMENT_MODES, default="fixed")
    fixed_monthly_salary = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    commission_percent = models.DecimalField(max_digits=5, decimal_places=2, default=30)
    nav_color = models.CharField(max_length=7, default="#1d4ed8")
    nav_background_color = models.CharField(max_length=7, default="#0f172a")
    nav_text_color = models.CharField(max_length=7, default="#eff6ff")
    is_active = models.BooleanField(default=True)
    can_login = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    joined_on = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("full_name",)

    def __str__(self):
        return f"{self.full_name} ({self.salon.name})"

    @property
    def owner_share_percent(self):
        value = 100 - float(self.commission_percent or 0)
        return max(0, value)


class WorkerIncentiveCampaign(models.Model):
    salon = models.ForeignKey(Salon, on_delete=models.CASCADE, related_name="worker_incentive_campaigns")
    title = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    bonus_percent = models.DecimalField(max_digits=5, decimal_places=2, default=10)
    valid_from = models.DateField()
    valid_to = models.DateField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.title} ({self.salon.name})"


class SalonVisit(models.Model):
    salon = models.ForeignKey(Salon, on_delete=models.CASCADE, related_name="visits")
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="visits")
    service = models.ForeignKey(SalonService, on_delete=models.SET_NULL, null=True, blank=True)
    services = models.ManyToManyField(SalonService, blank=True, related_name="visit_records")
    offer = models.ForeignKey(Offer, on_delete=models.SET_NULL, null=True, blank=True)
    assigned_worker = models.ForeignKey(Worker, on_delete=models.SET_NULL, null=True, blank=True, related_name="visits")
    visit_date = models.DateField()
    amount_paid = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    points_redeemed = models.PositiveIntegerField(default=0)
    points_discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-visit_date", "-id")

    def __str__(self):
        return f"{self.customer.full_name} visit on {self.visit_date}"

    @property
    def selected_services(self):
        services = list(self.services.all())
        if services:
            return services
        if self.service_id:
            return [self.service]
        return []

    @property
    def service_names_display(self):
        names = [service.name for service in self.selected_services]
        return ", ".join(names) if names else "-"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        customer = self.customer
        customer.total_visits = customer.visits.count()
        customer.last_visit = customer.visits.order_by("-visit_date").values_list("visit_date", flat=True).first()
        total_spend = customer.visits.aggregate(total=models.Sum("amount_paid")).get("total") or 0
        customer.total_spend = total_spend
        customer.save(update_fields=["total_visits", "last_visit", "total_spend"])


class Appointment(models.Model):
    STATUS_CHOICES = [
        ("booked", "Booked"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
        ("no_show", "No Show"),
    ]

    salon = models.ForeignKey(Salon, on_delete=models.CASCADE, related_name="appointments")
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name="appointments")
    service = models.ForeignKey(SalonService, on_delete=models.SET_NULL, null=True, blank=True, related_name="appointments")
    customer_name = models.CharField(max_length=160, blank=True)
    customer_phone = models.CharField(max_length=20, blank=True)
    appointment_at = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="booked")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("appointment_at", "-id")

    def __str__(self):
        display_name = self.customer.full_name if self.customer else (self.customer_name or "Customer")
        return f"{display_name} - {self.salon.name} ({self.appointment_at})"

    def save(self, *args, **kwargs):
        if self.customer and not self.customer_name:
            self.customer_name = self.customer.full_name
        if self.customer and not self.customer_phone:
            self.customer_phone = self.customer.phone
        super().save(*args, **kwargs)


class WhatsAppCampaign(models.Model):
    FILTER_CHOICES = [
        ("all", "All customers"),
        ("vip", "VIP customers"),
        ("high_spend", "High spenders"),
        ("inactive_60", "Inactive for 60 days"),
    ]

    salon = models.ForeignKey(Salon, on_delete=models.CASCADE, related_name="campaigns")
    offer = models.ForeignKey(Offer, on_delete=models.SET_NULL, null=True, blank=True)
    title = models.CharField(max_length=150)
    message = models.TextField()
    target_filter = models.CharField(max_length=20, choices=FILTER_CHOICES, default="all")
    sent_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.title} ({self.salon.name})"


class WebsiteSection(models.Model):
    SECTION_CHOICES = [
        ("about", "About"),
        ("promo", "Promo"),
        ("custom", "Custom"),
    ]
    salon = models.ForeignKey(Salon, on_delete=models.CASCADE, related_name="website_sections")
    section_type = models.CharField(max_length=20, choices=SECTION_CHOICES, default="custom")
    heading = models.CharField(max_length=160)
    body = models.TextField(blank=True)
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("display_order", "id")

    def __str__(self):
        return f"{self.heading} ({self.salon.name})"


class BeforeAfterGallery(models.Model):
    salon = models.ForeignKey(Salon, on_delete=models.CASCADE, related_name="before_after_items")
    title = models.CharField(max_length=160, blank=True)
    before_image = models.ImageField(upload_to="salons/gallery/before/")
    after_image = models.ImageField(upload_to="salons/gallery/after/")
    description = models.TextField(blank=True)
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("display_order", "id")

    def __str__(self):
        return self.title or f"Transformation #{self.id}"


class Testimonial(models.Model):
    salon = models.ForeignKey(Salon, on_delete=models.CASCADE, related_name="testimonials")
    customer_name = models.CharField(max_length=120)
    text = models.TextField()
    rating = models.PositiveIntegerField(default=5)
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("display_order", "id")

    def __str__(self):
        return f"{self.customer_name} ({self.salon.name})"


class POSBill(models.Model):
    PAYMENT_METHODS = [
        ("cash", "Cash"),
        ("upi", "UPI"),
        ("card", "Card"),
        ("mixed", "Mixed"),
    ]
    PAYMENT_STATUS = [
        ("paid", "Paid"),
        ("partial", "Partially Paid"),
        ("pending", "Pending"),
    ]

    salon = models.ForeignKey(Salon, on_delete=models.CASCADE, related_name="pos_bills")
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name="pos_bills")
    bill_number = models.CharField(max_length=30, unique=True)
    bill_date = models.DateTimeField(auto_now_add=True)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default="cash")
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default="paid")
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    amount_received = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    balance_due = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    # Loyalty points fields
    points_earned = models.PositiveIntegerField(default=0, help_text="Loyalty points earned from this bill")
    points_redeemed = models.PositiveIntegerField(default=0, help_text="Loyalty points redeemed for discount")
    points_discount = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Discount amount from redeemed points")
    receipt_sent = models.BooleanField(default=False, help_text="Whether digital receipt has been sent")
    receipt_sent_via = models.CharField(max_length=20, blank=True, help_text="How receipt was sent (whatsapp/email)")
    receipt_sent_at = models.DateTimeField(null=True, blank=True, help_text="When receipt was sent")

    class Meta:
        ordering = ("-bill_date", "-id")

    def __str__(self):
        return f"{self.bill_number} ({self.salon.name})"


class POSBillItem(models.Model):
    bill = models.ForeignKey(POSBill, on_delete=models.CASCADE, related_name="items")
    service = models.ForeignKey(SalonService, on_delete=models.SET_NULL, null=True, blank=True)
    item_name = models.CharField(max_length=160)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=8, decimal_places=2)
    line_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        ordering = ("id",)

    def __str__(self):
        return f"{self.item_name} x {self.quantity}"


class ProfitEntry(models.Model):
    ENTRY_TYPES = [
        ("expense", "Expense"),
        ("other_income", "Other Income"),
    ]

    salon = models.ForeignKey(Salon, on_delete=models.CASCADE, related_name="profit_entries")
    entry_date = models.DateField()
    entry_type = models.CharField(max_length=20, choices=ENTRY_TYPES, default="expense")
    title = models.CharField(max_length=160)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-entry_date", "-id")

    def __str__(self):
        return f"{self.title} ({self.get_entry_type_display()})"


class InventoryEntry(models.Model):
    UNIT_CHOICES = [
        ("pcs", "Pieces"),
        ("g", "Grams"),
        ("kg", "Kilograms"),
        ("ml", "Milliliters"),
        ("l", "Liters"),
        ("box", "Box"),
    ]

    salon = models.ForeignKey(Salon, on_delete=models.CASCADE, related_name="inventory_entries")
    item_name = models.CharField(max_length=160)
    category = models.CharField(max_length=120, blank=True)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit = models.CharField(max_length=20, choices=UNIT_CHOICES, default="pcs")
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    purchase_date = models.DateField()
    mark_as_expense = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-purchase_date", "-id")

    def __str__(self):
        return f"{self.item_name} ({self.quantity} {self.get_unit_display()})"

    def save(self, *args, **kwargs):
        qty = self.quantity or 0
        cost = self.unit_cost or 0
        self.total_cost = qty * cost
        super().save(*args, **kwargs)


class WorkerSalaryPayment(models.Model):
    salon = models.ForeignKey(Salon, on_delete=models.CASCADE, related_name="worker_salary_payments")
    worker = models.ForeignKey(Worker, on_delete=models.CASCADE, related_name="salary_payments")
    period_month = models.PositiveIntegerField()
    period_year = models.PositiveIntegerField()
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    paid_on = models.DateField()
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-paid_on", "-id")

    def __str__(self):
        return f"{self.worker.full_name} salary {self.period_month}/{self.period_year}"
