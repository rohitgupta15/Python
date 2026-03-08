from datetime import timedelta
from datetime import datetime

from django.utils import timezone

from .models import TaskEntry, UserReminderPreference


def reminder_popup_context(request):
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {"reminder_popup_tasks": []}

    preference, _ = UserReminderPreference.objects.get_or_create(user=request.user)
    if not preference.popup_enabled:
        return {"reminder_popup_tasks": []}

    now = timezone.now()
    session_key = f"reminder_popup_last_shown_{request.user.id}"
    last_shown_value = request.session.get(session_key)
    if last_shown_value:
        try:
            last_shown = datetime.fromisoformat(last_shown_value)
            if timezone.is_naive(last_shown):
                last_shown = timezone.make_aware(last_shown, timezone.get_current_timezone())
            delta = now - last_shown
            if delta.total_seconds() < max(preference.popup_interval_minutes, 1) * 60:
                return {"reminder_popup_tasks": []}
        except ValueError:
            pass

    tasks = TaskEntry.objects.filter(
        user=request.user,
        status="pending",
        popup_enabled=True,
        task_type__in=["todo", "reminder"],
    ).order_by("due_at", "-created_at")[:50]

    if preference.only_due_today:
        today = timezone.localdate()
        tasks = [task for task in tasks if task.due_at and timezone.localtime(task.due_at).date() == today]

    popup_tasks = []
    for task in tasks:
        if not task.due_at:
            continue
        due_at_local = timezone.localtime(task.due_at)
        trigger_time = due_at_local - timedelta(minutes=task.remind_before_minutes or 0)
        if now >= trigger_time:
            popup_tasks.append(task)
        if len(popup_tasks) >= 3:
            break

    if popup_tasks:
        request.session[session_key] = now.isoformat()

    return {"reminder_popup_tasks": popup_tasks}
