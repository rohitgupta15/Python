from .features.appointments import salon_appointments
from .features.campaigns import salon_whatsapp_campaign
from .features.customers import salon_customers
from .features.home_auth import (
    home,
    login_view,
    logout_view,
    password_reset_otp_request,
    password_reset_otp_verify,
    register_view,
)
from .features.inventory import salon_inventory
from .features.incentives import salon_incentive_campaigns
from .features.loyalty import (
    salon_loyalty_dashboard,
    salon_loyalty_settings,
    customer_loyalty_detail,
    adjust_customer_points,
    process_loyalty_for_bill,
)
from .features.offers import salon_offers
from .features.owner import owner_dashboard, salon_create, salon_edit, salon_public_page
from .features.pos import (
    salon_pos,
    salon_pos_bill_detail,
    salon_customer_search,
    salon_service_search,
)
from .features.receipts import (
    send_receipt_whatsapp,
    send_receipt_email,
    download_receipt_pdf,
    view_receipt_online,
)
from .features.reports import salon_reports
from .features.style_advisor import owner_style_advisor, worker_style_advisor
from .features.tasks import task_notes, task_reminders, task_todos
from .features.visits import salon_visits
from .features.workers import salon_workers
from .features.worker_portal import (
    worker_customers,
    worker_dashboard,
    worker_nav_color_update,
    worker_salary_slips,
    worker_visit_entry,
    worker_customer_search,
    worker_service_search,
)
