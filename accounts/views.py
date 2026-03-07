from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import ProfileForm
from employees.models import AuditLog


@login_required
def profile_view(request):

    user = request.user

    if request.method == "POST":
        form = ProfileForm(request.POST, instance=user)

        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully.")
            return redirect("accounts:profile")

    else:
        form = ProfileForm(instance=user)

    activities = AuditLog.objects.filter(
        performed_by=user
    ).order_by("-created_at")[:20]

    sessions = [
        {"device": "Chrome / Windows", "ip": "192.168.1.10", "last_seen": "Today"}
    ]

    return render(
        request,
        "accounts/profile.html",
        {
            "form": form,
            "activities": activities,
            "sessions": sessions,
        },
    )