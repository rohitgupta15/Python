from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django import forms
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from ..forms import (
    BeforeAfterGalleryForm,
    OwnerDashboardSettingForm,
    SalonFeatureForm,
    SalonForm,
    SalonPageConfigForm,
    SalonServiceForm,
    TestimonialForm,
    WebsiteSectionForm,
    _validate_uploaded_image,
)
from ..models import (
    BeforeAfterGallery,
    OwnerDashboardSetting,
    Salon,
    SalonFeature,
    SalonFeatureImage,
    Offer,
    SalonPageConfig,
    SalonService,
    SalonServiceImage,
    Testimonial,
    WebsiteSection,
)


@login_required
def owner_dashboard(request):
    salons_qs = (
        Salon.objects.filter(owner=request.user)
        .annotate(
            feature_count=Count("features", distinct=True),
            service_count=Count("services", distinct=True),
            customer_count=Count("customers", distinct=True),
            visit_count=Count("visits", distinct=True),
        )
        .order_by("name")
    )
    total_salons = salons_qs.count()
    approved_salons = salons_qs.filter(is_active=True).count()
    pending_salons = total_salons - approved_salons
    totals = salons_qs.aggregate(
        total_features=Count("features", distinct=True),
        total_services=Count("services", distinct=True),
        total_customers=Count("customers", distinct=True),
        total_visits=Count("visits", distinct=True),
    )
    salons = list(salons_qs)

    status_summary = {
        "Approved": {"count": 0, "services": 0, "customers": 0, "visits": 0},
        "Pending": {"count": 0, "services": 0, "customers": 0, "visits": 0},
    }
    visit_histogram_raw = [
        {"label": "0", "count": 0},
        {"label": "1 - 10", "count": 0},
        {"label": "11 - 30", "count": 0},
        {"label": "31 - 60", "count": 0},
        {"label": "60+", "count": 0},
    ]

    for salon in salons:
        bucket = "Approved" if salon.is_active else "Pending"
        status_summary[bucket]["count"] += 1
        status_summary[bucket]["services"] += salon.service_count
        status_summary[bucket]["customers"] += salon.customer_count
        status_summary[bucket]["visits"] += salon.visit_count

        visits = salon.visit_count
        if visits == 0:
            visit_histogram_raw[0]["count"] += 1
        elif visits <= 10:
            visit_histogram_raw[1]["count"] += 1
        elif visits <= 30:
            visit_histogram_raw[2]["count"] += 1
        elif visits <= 60:
            visit_histogram_raw[3]["count"] += 1
        else:
            visit_histogram_raw[4]["count"] += 1

    max_bucket_value = max((item["count"] for item in visit_histogram_raw), default=0)
    visit_histogram = []
    for item in visit_histogram_raw:
        percent = int((item["count"] / max_bucket_value) * 100) if max_bucket_value else 0
        visit_histogram.append(
            {
                "label": item["label"],
                "count": item["count"],
                "percent": percent,
            }
        )

    status_pivot = []
    for label in ("Approved", "Pending"):
        row = status_summary[label]
        share = int((row["count"] / total_salons) * 100) if total_salons else 0
        status_pivot.append(
            {
                "label": label,
                "count": row["count"],
                "services": row["services"],
                "customers": row["customers"],
                "visits": row["visits"],
                "share": share,
            }
        )

    top_salons = sorted(salons, key=lambda s: (s.visit_count, s.customer_count, s.service_count), reverse=True)[:5]
    dashboard_setting, _ = OwnerDashboardSetting.objects.get_or_create(owner=request.user)
    setting_form = OwnerDashboardSettingForm(instance=dashboard_setting)

    if request.method == "POST" and request.POST.get("form_type") == "dashboard_settings":
        setting_form = OwnerDashboardSettingForm(request.POST, instance=dashboard_setting)
        if setting_form.is_valid():
            setting_form.save()
            messages.success(request, "Owner dashboard settings updated.")
            return redirect("owner_dashboard")

    approved_pct = int((approved_salons / total_salons) * 100) if total_salons else 0
    pending_pct = 100 - approved_pct if total_salons else 0
    pie_chart_style = f"conic-gradient(#0f766e 0% {approved_pct}%, #f59e0b {approved_pct}% 100%)"

    show_pivot = dashboard_setting.show_pivot
    show_histogram = dashboard_setting.show_histogram
    show_pie = dashboard_setting.show_pie
    show_leaderboard = dashboard_setting.show_leaderboard
    if dashboard_setting.layout_style == "pivot_grid":
        show_pivot = True
    elif dashboard_setting.layout_style == "histogram":
        show_histogram = True
    elif dashboard_setting.layout_style == "pie":
        show_pie = True

    context = {
        "salons": salons,
        "owner_metrics": {
            "total_salons": total_salons,
            "approved_salons": approved_salons,
            "pending_salons": pending_salons,
            "total_features": totals["total_features"] or 0,
            "total_services": totals["total_services"] or 0,
            "total_customers": totals["total_customers"] or 0,
            "total_visits": totals["total_visits"] or 0,
        },
        "status_pivot": status_pivot,
        "visit_histogram": visit_histogram,
        "top_salons": top_salons,
        "dashboard_setting": dashboard_setting,
        "dashboard_setting_form": setting_form,
        "pie_chart_style": pie_chart_style,
        "approved_pct": approved_pct,
        "pending_pct": pending_pct,
        "show_pivot": show_pivot,
        "show_histogram": show_histogram,
        "show_pie": show_pie,
        "show_leaderboard": show_leaderboard,
    }
    return render(request, "salon/owner_dashboard.html", context)


@login_required
def salon_create(request):
    form = SalonForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        salon = form.save(commit=False)
        salon.owner = request.user
        salon.is_active = False
        salon.save()
        SalonPageConfig.objects.get_or_create(salon=salon)
        messages.success(request, "Salon created and submitted for admin approval.")
        return redirect("salon_edit", slug=salon.slug)
    return render(request, "salon/salon_create.html", {"form": form})


@login_required
def salon_edit(request, slug):
    salon = get_object_or_404(Salon, slug=slug, owner=request.user)
    config, _ = SalonPageConfig.objects.get_or_create(salon=salon)
    salon_form = SalonForm(instance=salon)
    config_form = SalonPageConfigForm(instance=config)
    feature_form = SalonFeatureForm()
    service_form = SalonServiceForm()
    section_form = WebsiteSectionForm()
    gallery_form = BeforeAfterGalleryForm()
    testimonial_form = TestimonialForm()

    if request.method == "POST":
        form_type = request.POST.get("form_type")
        if not salon.is_active and form_type != "salon":
            messages.error(request, "This saloon is pending admin approval. Only basic details can be updated now.")
            return redirect("salon_edit", slug=salon.slug)
        if form_type == "salon":
            salon_form = SalonForm(request.POST, request.FILES, instance=salon)
            if salon_form.is_valid():
                salon_form.save()
                messages.success(request, "Salon details updated.")
                return redirect("salon_edit", slug=salon.slug)
        elif form_type == "config":
            config_form = SalonPageConfigForm(request.POST, request.FILES, instance=config)
            if config_form.is_valid():
                config_form.save()
                messages.success(request, "Page configuration updated.")
                return redirect("salon_edit", slug=salon.slug)
        elif form_type == "feature":
            feature_form = SalonFeatureForm(request.POST, request.FILES)
            if feature_form.is_valid():
                feature = feature_form.save(commit=False)
                feature.salon = salon
                feature.save()
                try:
                    for index, upload in enumerate(request.FILES.getlist("feature_images")):
                        validated = _validate_uploaded_image(upload, "Feature image")
                        SalonFeatureImage.objects.create(feature=feature, image=validated, display_order=index)
                except forms.ValidationError as exc:
                    feature.delete()
                    messages.error(request, exc.message)
                    return redirect("salon_edit", slug=salon.slug)
                messages.success(request, "Feature added.")
                return redirect("salon_edit", slug=salon.slug)
        elif form_type == "service":
            service_form = SalonServiceForm(request.POST, request.FILES)
            if service_form.is_valid():
                service = service_form.save(commit=False)
                service.salon = salon
                service.save()
                try:
                    for index, upload in enumerate(request.FILES.getlist("service_images")):
                        validated = _validate_uploaded_image(upload, "Service image")
                        SalonServiceImage.objects.create(service=service, image=validated, display_order=index)
                except forms.ValidationError as exc:
                    service.delete()
                    messages.error(request, exc.message)
                    return redirect("salon_edit", slug=salon.slug)
                messages.success(request, "Service added.")
                return redirect("salon_edit", slug=salon.slug)
        elif form_type == "delete_feature":
            feature = get_object_or_404(SalonFeature, id=request.POST.get("feature_id"), salon=salon)
            feature.delete()
            messages.success(request, "Feature removed.")
            return redirect("salon_edit", slug=salon.slug)
        elif form_type == "delete_service":
            service = get_object_or_404(SalonService, id=request.POST.get("service_id"), salon=salon)
            service.delete()
            messages.success(request, "Service removed.")
            return redirect("salon_edit", slug=salon.slug)
        elif form_type == "section":
            section_form = WebsiteSectionForm(request.POST)
            if section_form.is_valid():
                section = section_form.save(commit=False)
                section.salon = salon
                section.save()
                messages.success(request, "Website section added.")
                return redirect("salon_edit", slug=salon.slug)
        elif form_type == "delete_section":
            section = get_object_or_404(WebsiteSection, id=request.POST.get("section_id"), salon=salon)
            section.delete()
            messages.success(request, "Section removed.")
            return redirect("salon_edit", slug=salon.slug)
        elif form_type == "reorder_sections":
            section_ids = [item for item in request.POST.get("section_order", "").split(",") if item.strip()]
            for index, section_id in enumerate(section_ids):
                WebsiteSection.objects.filter(id=section_id, salon=salon).update(display_order=index)
            messages.success(request, "Section order updated.")
            return redirect("salon_edit", slug=salon.slug)
        elif form_type == "gallery":
            gallery_form = BeforeAfterGalleryForm(request.POST, request.FILES)
            if gallery_form.is_valid():
                item = gallery_form.save(commit=False)
                item.salon = salon
                item.save()
                messages.success(request, "Before/After item added.")
                return redirect("salon_edit", slug=salon.slug)
        elif form_type == "delete_gallery":
            item = get_object_or_404(BeforeAfterGallery, id=request.POST.get("gallery_id"), salon=salon)
            item.delete()
            messages.success(request, "Gallery item removed.")
            return redirect("salon_edit", slug=salon.slug)
        elif form_type == "testimonial":
            testimonial_form = TestimonialForm(request.POST)
            if testimonial_form.is_valid():
                testimonial = testimonial_form.save(commit=False)
                testimonial.salon = salon
                testimonial.save()
                messages.success(request, "Testimonial added.")
                return redirect("salon_edit", slug=salon.slug)
        elif form_type == "delete_testimonial":
            testimonial = get_object_or_404(Testimonial, id=request.POST.get("testimonial_id"), salon=salon)
            testimonial.delete()
            messages.success(request, "Testimonial removed.")
            return redirect("salon_edit", slug=salon.slug)

    context = {
        "salon": salon,
        "salon_form": salon_form,
        "config_form": config_form,
        "feature_form": feature_form,
        "service_form": service_form,
        "section_form": section_form,
        "gallery_form": gallery_form,
        "testimonial_form": testimonial_form,
        "features": salon.features.all(),
        "services": salon.services.all(),
        "sections": salon.website_sections.all(),
        "gallery_items": salon.before_after_items.all(),
        "testimonials": salon.testimonials.all(),
    }
    return render(request, "salon/salon_edit.html", context)


def salon_public_page(request, slug):
    salon = get_object_or_404(Salon, slug=slug, is_active=True)
    config, _ = SalonPageConfig.objects.get_or_create(salon=salon)
    today = timezone.localdate()
    features = salon.features.prefetch_related("gallery_images").all()
    services = salon.services.filter(is_active=True).prefetch_related("gallery_images")
    offers = salon.offers.filter(is_active=True, valid_from__lte=today, valid_to__gte=today).order_by("valid_to", "title")
    sections = salon.website_sections.filter(is_active=True)
    gallery_items = salon.before_after_items.filter(is_active=True)
    testimonials = salon.testimonials.filter(is_active=True)
    return render(
        request,
        "salon/salon_public_page.html",
        {
            "salon": salon,
            "config": config,
            "features": features,
            "services": services,
            "offers": offers,
            "sections": sections,
            "gallery_items": gallery_items,
            "testimonials": testimonials,
        },
    )
