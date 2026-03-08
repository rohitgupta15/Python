from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from ..forms import TaskEntryForm, UserReminderPreferenceForm
from ..models import Salon, TaskEntry, UserReminderPreference, Worker


TAB_TO_TASK_TYPE = {
    "todos": "todo",
    "notes": "note",
    "reminders": "reminder",
}
PAGE_SIZE = 10


def _tab_meta(tab):
    meta = {
        "todos": ("To-Do List", "Track actionable tasks and complete them on time."),
        "notes": ("Notes", "Store quick notes and important context."),
        "reminders": ("Reminders", "Manage timed reminders and popup preferences."),
    }
    return meta.get(tab, meta["todos"])


def _primary_salon_for_user(user):
    owner_salon = Salon.objects.filter(owner=user).order_by("name").first()
    if owner_salon:
        return owner_salon
    worker = Worker.objects.select_related("salon").filter(user=user, is_deleted=False).first()
    if worker:
        return worker.salon
    return None


@login_required
def task_board(request, tab):
    if tab not in TAB_TO_TASK_TYPE:
        return redirect("task_todos")

    task_type = TAB_TO_TASK_TYPE[tab]
    title, subtitle = _tab_meta(tab)
    nav_salon = _primary_salon_for_user(request.user)
    worker_profile = Worker.objects.select_related("salon").filter(
        user=request.user, can_login=True, is_active=True, is_deleted=False
    ).first()
    is_worker_user = worker_profile is not None
    reminder_preference, _ = UserReminderPreference.objects.get_or_create(user=request.user)
    task_form = TaskEntryForm()
    preference_form = UserReminderPreferenceForm(instance=reminder_preference)

    if request.method == "POST":
        form_type = (request.POST.get("form_type") or "").strip()
        if form_type == "create_task":
            task_form = TaskEntryForm(request.POST)
            if task_form.is_valid():
                task = task_form.save(commit=False)
                task.user = request.user
                task.salon = nav_salon
                task.task_type = task_type
                task.save()
                messages.success(request, f"{title[:-1] if title.endswith('s') else title} item created.")
                return redirect(f"task_{tab}")
        elif form_type == "save_preferences":
            preference_form = UserReminderPreferenceForm(request.POST, instance=reminder_preference)
            if preference_form.is_valid():
                preference_form.save()
                messages.success(request, "Reminder popup preferences updated.")
                return redirect(f"task_{tab}")
        elif form_type in {"complete_task", "reopen_task", "delete_task"}:
            task = get_object_or_404(TaskEntry, id=request.POST.get("task_id"), user=request.user, task_type=task_type)
            if form_type == "complete_task":
                task.status = "completed"
                task.save(update_fields=["status", "updated_at"])
                messages.success(request, "Task marked as completed.")
            elif form_type == "reopen_task":
                task.status = "pending"
                task.save(update_fields=["status", "updated_at"])
                messages.success(request, "Task reopened.")
            else:
                task.delete()
                messages.success(request, "Task deleted.")
            return redirect(f"task_{tab}")

    tasks = TaskEntry.objects.filter(user=request.user, task_type=task_type).order_by("-created_at")
    pending_tasks_qs = tasks.filter(status="pending")
    completed_tasks_qs = tasks.filter(status="completed")

    pending_page = request.GET.get("pending_page") or "1"
    completed_page = request.GET.get("completed_page") or "1"
    pending_tasks = Paginator(pending_tasks_qs, PAGE_SIZE).get_page(pending_page)
    completed_tasks = Paginator(completed_tasks_qs, PAGE_SIZE).get_page(completed_page)

    pending_query_params = request.GET.copy()
    pending_query_params.pop("pending_page", None)
    completed_query_params = request.GET.copy()
    completed_query_params.pop("completed_page", None)

    context = {
        "tab": tab,
        "title": title,
        "subtitle": subtitle,
        "task_form": task_form,
        "preference_form": preference_form,
        "pending_tasks": pending_tasks,
        "completed_tasks": completed_tasks,
        "nav_salon": nav_salon,
        "is_worker_user": is_worker_user,
        "worker_profile": worker_profile,
        "pending_querystring": pending_query_params.urlencode(),
        "completed_querystring": completed_query_params.urlencode(),
    }
    return render(request, "salon/task_board.html", context)


@login_required
def task_todos(request):
    return task_board(request, "todos")


@login_required
def task_notes(request):
    return task_board(request, "notes")


@login_required
def task_reminders(request):
    return task_board(request, "reminders")
