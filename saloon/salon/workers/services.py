from datetime import datetime
from decimal import Decimal

from django.db.models import Sum


def parse_month_key(month_key):
    try:
        dt = datetime.strptime(month_key, "%Y-%m")
        return dt.year, dt.month
    except Exception:
        now = datetime.now()
        return now.year, now.month


def build_worker_cards(salon, workers, salary_payments, year, month, incentive_campaigns=None):
    incentive_campaigns = incentive_campaigns or []
    worker_cards = []
    for worker in workers:
        worker_visits = salon.visits.filter(assigned_worker=worker, visit_date__year=year, visit_date__month=month)
        visit_sales = (
            worker_visits
            .aggregate(total=Sum("amount_paid"))
            .get("total")
            or Decimal("0.00")
        )
        commission_due = (visit_sales * (worker.commission_percent or 0)) / Decimal("100")
        incentive_amount = Decimal("0.00")
        applied_campaigns = []
        for campaign in incentive_campaigns:
            campaign_sales = (
                worker_visits.filter(visit_date__range=(campaign.valid_from, campaign.valid_to))
                .aggregate(total=Sum("amount_paid"))
                .get("total")
                or Decimal("0.00")
            )
            if campaign_sales <= 0:
                continue
            incentive_amount += (campaign_sales * (campaign.bonus_percent or 0)) / Decimal("100")
            applied_campaigns.append(campaign)

        owner_share = visit_sales - commission_due - incentive_amount
        if worker.payment_mode == "fixed":
            base_due_amount = worker.fixed_monthly_salary or Decimal("0.00")
        else:
            base_due_amount = commission_due
        due_amount = base_due_amount + incentive_amount
        paid_amount = (
            salary_payments.filter(worker=worker).aggregate(total=Sum("amount_paid")).get("total") or Decimal("0.00")
        )
        balance_due = due_amount - paid_amount
        worker_cards.append(
            {
                "worker": worker,
                "visit_sales": visit_sales,
                "commission_due": commission_due,
                "incentive_amount": incentive_amount,
                "applied_campaigns": applied_campaigns,
                "owner_share": owner_share,
                "base_due_amount": base_due_amount,
                "due_amount": due_amount,
                "paid_amount": paid_amount,
                "balance_due": balance_due,
            }
        )
    return worker_cards
