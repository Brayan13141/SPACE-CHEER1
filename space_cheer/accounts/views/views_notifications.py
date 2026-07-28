from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from accounts.services.notification_service import ManagementNotificationService


@login_required
def notifications(request):
    qs = ManagementNotificationService.management_qs(request.user)
    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "accounts/notifications.html", {"page_obj": page_obj})


@login_required
@require_POST
def notification_read(request, pk):
    notification = ManagementNotificationService.mark_read(request.user, pk)
    if notification.url:
        return redirect(notification.url)
    return redirect("accounts:notifications")


@login_required
@require_POST
def notifications_read_all(request):
    ManagementNotificationService.mark_all_read(request.user)
    return redirect("accounts:notifications")
