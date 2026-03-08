from datetime import timedelta
from decimal import Decimal
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Sum
from django.db.models.functions import TruncDate, TruncWeek
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date

from ..forms import InventoryEntryForm, ProfitEntryForm, ReportBuilderSettingForm
from ..models import ReportBuilderSetting
from .helpers import get_approved_owner_salon


def _get_period_dates(period):
    today = timezone.localdate()
    if period == "weekly":
        start_date = today - timedelta(days=today.weekday())
        end_date = today
    elif period == "monthly":
        start_date = today.replace(day=1)
        end_date = today
    else:
        start_date = today
        end_date = today
    return start_date, end_date


def _shift_month(month_start, offset):
    total_months = month_start.year * 12 + (month_start.month - 1) + offset
    year = total_months // 12
    month = total_months % 12 + 1
    return month_start.replace(year=year, month=month, day=1)


def _month_start(value):
    return value.replace(day=1)


def _week_start(value):
    return value - timedelta(days=value.weekday())


def _accumulate_bucket(rows, date_index, amount_index, bucket_fn):
    bucket_map = {}
    zero = Decimal("0.00")
    for row in rows:
        row_date = row[date_index]
        if not row_date:
            continue
        if hasattr(row_date, "date"):
            row_date = row_date.date()
        bucket = bucket_fn(row_date)
        amount = row[amount_index] or zero
        bucket_map[bucket] = bucket_map.get(bucket, zero) + amount
    return bucket_map


@login_required
def salon_reports(request, slug):
    salon = get_approved_owner_salon(request, slug)
    period = (request.GET.get("period") or "daily").strip().lower()
    if period not in {"daily", "weekly", "monthly"}:
        period = "daily"
    start_date, end_date = _get_period_dates(period)
    bill_date_from = (request.GET.get("bill_date_from") or "").strip()
    bill_date_to = (request.GET.get("bill_date_to") or "").strip()
    report_setting, _ = ReportBuilderSetting.objects.get_or_create(salon=salon)

    form = ProfitEntryForm(request.POST or None, initial={"entry_date": timezone.localdate()})
    inventory_form = InventoryEntryForm(request.POST or None, initial={"purchase_date": timezone.localdate()})
    report_setting_form = ReportBuilderSettingForm(instance=report_setting)
    if request.method == "POST":
        form_type = request.POST.get("form_type")
        if form_type == "report_settings":
            report_setting_form = ReportBuilderSettingForm(request.POST, instance=report_setting)
            if report_setting_form.is_valid():
                report_setting_form.save()
                messages.success(request, "Report builder settings updated.")
                return redirect(f"{reverse('salon_reports', kwargs={'slug': salon.slug})}?period={period}")
        if form_type == "add_profit_entry" and form.is_valid():
            entry = form.save(commit=False)
            entry.salon = salon
            entry.save()
            messages.success(request, "Profit entry added.")
            return redirect(f"{reverse('salon_reports', kwargs={'slug': salon.slug})}?period={period}")
        if form_type == "add_inventory_entry" and inventory_form.is_valid():
            inventory = inventory_form.save(commit=False)
            inventory.salon = salon
            inventory.save()
            messages.success(request, "Inventory item added.")
            return redirect(f"{reverse('salon_reports', kwargs={'slug': salon.slug})}?period={period}")

    bills = salon.pos_bills.filter(bill_date__date__range=(start_date, end_date))
    bill_start = parse_date(bill_date_from) if bill_date_from else None
    bill_end = parse_date(bill_date_to) if bill_date_to else None
    if bill_start and bill_end and bill_start > bill_end:
        bill_start, bill_end = bill_end, bill_start
        bill_date_from, bill_date_to = bill_start.isoformat(), bill_end.isoformat()
    if bill_start:
        bills = bills.filter(bill_date__date__gte=bill_start)
    if bill_end:
        bills = bills.filter(bill_date__date__lte=bill_end)
    visits = salon.visits.filter(visit_date__range=(start_date, end_date))
    profit_entries = salon.profit_entries.filter(entry_date__range=(start_date, end_date))
    inventory_entries = salon.inventory_entries.filter(purchase_date__range=(start_date, end_date))
    expense_inventory_entries = inventory_entries.filter(mark_as_expense=True)
    bill_page_size = 20
    bill_paginator = Paginator(bills.select_related("customer"), bill_page_size)
    bills_page = bill_paginator.get_page(request.GET.get("bill_page"))
    bill_filter_query = urlencode(
        {
            "period": period,
            "bill_date_from": bill_date_from,
            "bill_date_to": bill_date_to,
        }
    )

    sales_total = bills.aggregate(total=Sum("total_amount")).get("total") or Decimal("0.00")
    received_total = bills.aggregate(total=Sum("amount_received")).get("total") or Decimal("0.00")
    pending_total = bills.aggregate(total=Sum("balance_due")).get("total") or Decimal("0.00")
    visit_total = visits.aggregate(total=Sum("amount_paid")).get("total") or Decimal("0.00")
    manual_expense_total = (
        profit_entries.filter(entry_type="expense").aggregate(total=Sum("amount")).get("total") or Decimal("0.00")
    )
    inventory_expense_total = expense_inventory_entries.aggregate(total=Sum("total_cost")).get("total") or Decimal("0.00")
    expense_total = manual_expense_total + inventory_expense_total
    other_income_total = (
        profit_entries.filter(entry_type="other_income").aggregate(total=Sum("amount")).get("total") or Decimal("0.00")
    )
    net_profit = received_total + other_income_total - expense_total
    monthly_inventory_rows = salon.inventory_entries.filter(purchase_date__year=end_date.year).values_list(
        "purchase_date",
        "total_cost",
        "mark_as_expense",
    )
    monthly_inventory_map = {}
    for purchase_date, total_cost, mark_as_expense in monthly_inventory_rows:
        if not purchase_date:
            continue
        bucket = _month_start(purchase_date)
        if bucket not in monthly_inventory_map:
            monthly_inventory_map[bucket] = {
                "month": bucket,
                "monthly_total_cost": Decimal("0.00"),
                "monthly_expense_cost": Decimal("0.00"),
            }
        cost = total_cost or Decimal("0.00")
        monthly_inventory_map[bucket]["monthly_total_cost"] += cost
        if mark_as_expense:
            monthly_inventory_map[bucket]["monthly_expense_cost"] += cost
    monthly_inventory = sorted(monthly_inventory_map.values(), key=lambda item: item["month"], reverse=True)
    today = timezone.localdate()
    current_month = today.replace(day=1)

    def _to_date(bucket):
        return bucket.date() if hasattr(bucket, "date") else bucket

    chart_points = []
    max_chart_value = Decimal("1.00")
    if period == "daily":
        chart_start = today - timedelta(days=6)
        sales_rows = (
            salon.pos_bills.filter(bill_date__date__range=(chart_start, today))
            .annotate(bucket=TruncDate("bill_date"))
            .values("bucket")
            .annotate(total=Sum("total_amount"))
        )
        sales_map = {_to_date(row["bucket"]): row["total"] or Decimal("0.00") for row in sales_rows}
        manual_expense_rows = salon.profit_entries.filter(
            entry_date__range=(chart_start, today),
            entry_type="expense",
        ).values_list("entry_date", "amount")
        inventory_expense_rows = salon.inventory_entries.filter(
            purchase_date__range=(chart_start, today),
            mark_as_expense=True,
        ).values_list("purchase_date", "total_cost")
        manual_expense_map = _accumulate_bucket(manual_expense_rows, 0, 1, lambda value: value)
        inventory_expense_map = _accumulate_bucket(inventory_expense_rows, 0, 1, lambda value: value)
        for idx in range(7):
            day = chart_start + timedelta(days=idx)
            sale_value = sales_map.get(day, Decimal("0.00"))
            expense_value = manual_expense_map.get(day, Decimal("0.00")) + inventory_expense_map.get(day, Decimal("0.00"))
            max_chart_value = max(max_chart_value, sale_value, expense_value)
            chart_points.append(
                {
                    "label": day.strftime("%d %b"),
                    "sale_value": sale_value,
                    "expense_value": expense_value,
                }
            )
    elif period == "weekly":
        week_start = today - timedelta(days=today.weekday())
        chart_start = week_start - timedelta(weeks=7)
        sales_rows = (
            salon.pos_bills.filter(bill_date__date__gte=chart_start)
            .annotate(bucket=TruncWeek("bill_date"))
            .values("bucket")
            .annotate(total=Sum("total_amount"))
        )
        sales_map = {_to_date(row["bucket"]): row["total"] or Decimal("0.00") for row in sales_rows}
        manual_expense_rows = salon.profit_entries.filter(
            entry_date__gte=chart_start,
            entry_type="expense",
        ).values_list("entry_date", "amount")
        inventory_expense_rows = salon.inventory_entries.filter(
            purchase_date__gte=chart_start,
            mark_as_expense=True,
        ).values_list("purchase_date", "total_cost")
        manual_expense_map = _accumulate_bucket(manual_expense_rows, 0, 1, _week_start)
        inventory_expense_map = _accumulate_bucket(inventory_expense_rows, 0, 1, _week_start)
        for idx in range(8):
            start_of_week = chart_start + timedelta(weeks=idx)
            sale_value = sales_map.get(start_of_week, Decimal("0.00"))
            expense_value = manual_expense_map.get(start_of_week, Decimal("0.00")) + inventory_expense_map.get(
                start_of_week, Decimal("0.00")
            )
            max_chart_value = max(max_chart_value, sale_value, expense_value)
            chart_points.append(
                {
                    "label": start_of_week.strftime("%d %b"),
                    "sale_value": sale_value,
                    "expense_value": expense_value,
                }
            )
    else:
        start_12_month = _shift_month(current_month, -11)
        sales_month_rows = (
            salon.pos_bills.filter(bill_date__date__gte=start_12_month)
            .annotate(bucket=TruncDate("bill_date"))
            .values("bucket")
            .annotate(total=Sum("total_amount"))
        )
        sales_map = {}
        for row in sales_month_rows:
            bucket = _to_date(row["bucket"])
            if not bucket:
                continue
            bucket = _month_start(bucket)
            sales_map[bucket] = sales_map.get(bucket, Decimal("0.00")) + (row["total"] or Decimal("0.00"))
        manual_expense_rows = salon.profit_entries.filter(
            entry_date__gte=start_12_month,
            entry_type="expense",
        ).values_list("entry_date", "amount")
        inventory_expense_rows = salon.inventory_entries.filter(
            purchase_date__gte=start_12_month,
            mark_as_expense=True,
        ).values_list("purchase_date", "total_cost")
        manual_expense_map = _accumulate_bucket(manual_expense_rows, 0, 1, _month_start)
        inventory_expense_map = _accumulate_bucket(inventory_expense_rows, 0, 1, _month_start)
        for idx in range(12):
            month_date = _shift_month(start_12_month, idx)
            sale_value = sales_map.get(month_date, Decimal("0.00"))
            expense_value = manual_expense_map.get(month_date, Decimal("0.00")) + inventory_expense_map.get(
                month_date, Decimal("0.00")
            )
            max_chart_value = max(max_chart_value, sale_value, expense_value)
            chart_points.append(
                {
                    "label": month_date.strftime("%b"),
                    "sale_value": sale_value,
                    "expense_value": expense_value,
                }
            )
    for point in chart_points:
        point["sale_height"] = int((point["sale_value"] / max_chart_value) * 100) if max_chart_value else 0
        point["expense_height"] = int((point["expense_value"] / max_chart_value) * 100) if max_chart_value else 0

    sales_value_for_ratio = sales_total if sales_total > 0 else Decimal("1.00")
    expense_ratio = int((expense_total / sales_value_for_ratio) * 100) if sales_total > 0 else 0
    expense_ratio = max(0, min(100, expense_ratio))
    pending_ratio = int((pending_total / sales_value_for_ratio) * 100) if sales_total > 0 else 0
    pending_ratio = max(0, min(100, pending_ratio))
    received_ratio = 100 - pending_ratio

    prev_month_start = _shift_month(current_month, -1)
    prev_month_end = current_month - timedelta(days=1)
    last_month_sale = (
        salon.pos_bills.filter(bill_date__date__range=(prev_month_start, prev_month_end)).aggregate(total=Sum("total_amount")).get("total")
        or Decimal("0.00")
    )
    total_customer_count = salon.customers.count()
    year_start = today.replace(month=1, day=1)
    yearly_sales = salon.pos_bills.filter(bill_date__date__range=(year_start, today)).aggregate(total=Sum("total_amount")).get("total") or Decimal("0.00")
    yearly_profit = (
        (salon.pos_bills.filter(bill_date__date__range=(year_start, today)).aggregate(total=Sum("amount_received")).get("total") or Decimal("0.00"))
        + (salon.profit_entries.filter(entry_date__range=(year_start, today), entry_type="other_income").aggregate(total=Sum("amount")).get("total") or Decimal("0.00"))
        - (
            (salon.profit_entries.filter(entry_date__range=(year_start, today), entry_type="expense").aggregate(total=Sum("amount")).get("total") or Decimal("0.00"))
            + (salon.inventory_entries.filter(purchase_date__range=(year_start, today), mark_as_expense=True).aggregate(total=Sum("total_cost")).get("total") or Decimal("0.00"))
        )
    )
    yearly_visits = salon.visits.filter(visit_date__range=(year_start, today)).count()
    total_worker_count = salon.workers.filter(is_deleted=False).count()
    inventory_total_cost = inventory_entries.aggregate(total=Sum("total_cost")).get("total") or Decimal("0.00")
    profit_value = net_profit if net_profit > 0 else Decimal("0.00")
    loss_value = (-net_profit) if net_profit < 0 else Decimal("0.00")

    show_metrics_summary = report_setting.show_metrics_summary
    show_entry_forms = report_setting.show_entry_forms
    show_profit_entries = report_setting.show_profit_entries
    show_inventory_list = report_setting.show_inventory_list
    show_monthly_inventory = report_setting.show_monthly_inventory
    show_sales_bills = report_setting.show_sales_bills
    show_kpi_strip = report_setting.show_kpi_strip
    show_sales_expense_chart = report_setting.show_sales_expense_chart
    show_expense_donut = report_setting.show_expense_donut
    show_collections_donut = report_setting.show_collections_donut
    show_mini_cards = report_setting.show_mini_cards
    show_metric_customers = report_setting.show_metric_customers
    show_metric_profit = report_setting.show_metric_profit
    show_metric_loss = report_setting.show_metric_loss
    show_metric_expense = report_setting.show_metric_expense
    show_metric_workers = report_setting.show_metric_workers
    show_metric_inventory = report_setting.show_metric_inventory

    context = {
        "salon": salon,
        "period": period,
        "start_date": start_date,
        "end_date": end_date,
        "form": form,
        "inventory_form": inventory_form,
        "report_setting": report_setting,
        "report_setting_form": report_setting_form,
        "show_metrics_summary": show_metrics_summary,
        "show_entry_forms": show_entry_forms,
        "show_profit_entries": show_profit_entries,
        "show_inventory_list": show_inventory_list,
        "show_monthly_inventory": show_monthly_inventory,
        "show_sales_bills": show_sales_bills,
        "show_kpi_strip": show_kpi_strip,
        "show_sales_expense_chart": show_sales_expense_chart,
        "show_expense_donut": show_expense_donut,
        "show_collections_donut": show_collections_donut,
        "show_mini_cards": show_mini_cards,
        "show_metric_customers": show_metric_customers,
        "show_metric_profit": show_metric_profit,
        "show_metric_loss": show_metric_loss,
        "show_metric_expense": show_metric_expense,
        "show_metric_workers": show_metric_workers,
        "show_metric_inventory": show_metric_inventory,
        "bills_page": bills_page,
        "bill_date_from": bill_date_from,
        "bill_date_to": bill_date_to,
        "bill_filter_query": bill_filter_query,
        "profit_entries": profit_entries[:50],
        "inventory_entries": inventory_entries[:50],
        "monthly_inventory": monthly_inventory,
        "chart_points": chart_points,
        "expense_ratio": expense_ratio,
        "received_ratio": received_ratio,
        "pending_ratio": pending_ratio,
        "last_month_sale": last_month_sale,
        "total_customer_count": total_customer_count,
        "total_worker_count": total_worker_count,
        "inventory_total_cost": inventory_total_cost,
        "profit_value": profit_value,
        "loss_value": loss_value,
        "yearly_sales": yearly_sales,
        "yearly_profit": yearly_profit,
        "yearly_visits": yearly_visits,
        "sales_total": sales_total,
        "received_total": received_total,
        "pending_total": pending_total,
        "visit_total": visit_total,
        "manual_expense_total": manual_expense_total,
        "inventory_expense_total": inventory_expense_total,
        "expense_total": expense_total,
        "other_income_total": other_income_total,
        "net_profit": net_profit,
    }
    return render(request, "salon/salon_reports.html", context)
