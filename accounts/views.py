import uuid

from django.contrib.auth.decorators import login_required
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.models import User
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings as django_settings

from .forms import ProfileForm
from .permissions import role_required, perm_required
from employees.models import AuditLog
from companies.models import OrganisationUser, UserInvite


# ── helpers ──────────────────────────────────────────────

def get_org_user(request):
    return request.user.organisation_user


# ── PROFILE ───────────────────────────────────────────────

@login_required
def profile_view(request):
    user     = request.user
    org_user = get_org_user(request)

    if request.method == "POST":
        action = request.POST.get("action", "update_profile")

        if action == "update_profile":
            form = ProfileForm(request.POST, instance=user)
            if form.is_valid():
                form.save()
                AuditLog.objects.create(
                    action="Profile Updated",
                    description=f"{user.username} updated their profile.",
                    performed_by=user,
                )
                messages.success(request, "Profile updated successfully.")
                return redirect("accounts:profile")

        elif action == "change_password":
            current = request.POST.get("current_password", "")
            new1    = request.POST.get("new_password1", "")
            new2    = request.POST.get("new_password2", "")
            if not user.check_password(current):
                messages.error(request, "Current password is incorrect.")
            elif new1 != new2:
                messages.error(request, "New passwords do not match.")
            elif len(new1) < 8:
                messages.error(request, "Password must be at least 8 characters.")
            else:
                user.set_password(new1)
                user.save()
                update_session_auth_hash(request, user)
                AuditLog.objects.create(
                    action="Password Changed",
                    description=f"{user.username} changed their password.",
                    performed_by=user,
                )
                messages.success(request, "Password changed successfully.")
            return redirect("accounts:profile")

        form = ProfileForm(instance=user)
    else:
        form = ProfileForm(instance=user)

    activities = AuditLog.objects.filter(
        performed_by=user
    ).order_by("-created_at")[:20]

    return render(request, "accounts/profile.html", {
        "form":       form,
        "activities": activities,
        "org_user":   org_user,
    })


# ── SETTINGS ─────────────────────────────────────────────

@role_required("ADMIN")
def settings_view(request):
    org_user = get_org_user(request)
    org      = org_user.organisation

    members = OrganisationUser.objects.filter(
        organisation=org
    ).select_related("user").order_by("role", "user__username")

    invites = UserInvite.objects.filter(
        organisation=org, status="PENDING"
    ).order_by("-created_at")

    return render(request, "accounts/settings.html", {
        "org_user": org_user,
        "members":  members,
        "invites":  invites,
        "org":      org,
    })


# ── INVITE USER ───────────────────────────────────────────

@role_required("ADMIN")
def invite_user(request):
    if request.method != "POST":
        return redirect("accounts:settings")

    org   = get_org_user(request).organisation
    email = request.POST.get("email", "").strip().lower()
    role  = request.POST.get("role", "SUPERVISOR")

    if not email:
        messages.error(request, "Email is required.")
        return redirect("accounts:settings")

    if OrganisationUser.objects.filter(
        organisation=org, user__email=email
    ).exists():
        messages.warning(request, f"{email} is already a member.")
        return redirect("accounts:settings")

    invite, created = UserInvite.objects.get_or_create(
        organisation=org,
        email=email,
        defaults={"role": role, "invited_by": request.user},
    )

    if not created:
        invite.token      = uuid.uuid4()
        invite.role       = role
        invite.status     = "PENDING"
        invite.invited_by = request.user
        invite.save()

    invite_url = request.build_absolute_uri(
        f"/accounts/accept-invite/{invite.token}/"
    )

    try:
        send_mail(
            subject=f"You're invited to join {org.name} on Salary Engine",
            message=(
                f"Hi,\n\n"
                f"You have been invited to join {org.name} as {invite.get_role_display()}.\n\n"
                f"Accept here: {invite_url}\n\n"
                f"Invited by {request.user.get_full_name() or request.user.username}."
            ),
            from_email=getattr(django_settings, "DEFAULT_FROM_EMAIL", "noreply@salaryengine.com"),
            recipient_list=[email],
            fail_silently=True,
        )
    except Exception:
        pass

    AuditLog.objects.create(
        action="User Invited",
        description=f"{request.user.username} invited {email} as {role}.",
        performed_by=request.user,
    )
    messages.success(request, f"Invite sent to {email}.")
    return redirect("accounts:settings")


# ── ACCEPT INVITE ─────────────────────────────────────────

def accept_invite(request, token):
    invite = get_object_or_404(UserInvite, token=token, status="PENDING")

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password1", "")
        confirm  = request.POST.get("password2", "")

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already taken.")
        elif password != confirm:
            messages.error(request, "Passwords do not match.")
        elif len(password) < 8:
            messages.error(request, "Password must be at least 8 characters.")
        else:
            user = User.objects.create_user(
                username=username,
                email=invite.email,
                password=password,
            )
            OrganisationUser.objects.create(
                user=user,
                organisation=invite.organisation,
                role=invite.role,
            )
            invite.status = "ACCEPTED"
            invite.save()
            AuditLog.objects.create(
                action="Invite Accepted",
                description=f"{username} accepted invite to {invite.organisation.name}.",
                performed_by=user,
            )
            messages.success(request, "Account created! You can now log in.")
            return redirect("login")

    return render(request, "accounts/accept_invite.html", {"invite": invite})


# ── CHANGE ROLE ───────────────────────────────────────────

@role_required("ADMIN")
def change_role(request, member_id):
    if request.method != "POST":
        return redirect("accounts:settings")

    org      = get_org_user(request).organisation
    member   = get_object_or_404(OrganisationUser, id=member_id, organisation=org)
    new_role = request.POST.get("role")

    if member.user == request.user:
        messages.error(request, "You cannot change your own role.")
        return redirect("accounts:settings")

    if new_role in dict(OrganisationUser.ROLE_CHOICES):
        old_role    = member.role
        member.role = new_role
        member.save()
        AuditLog.objects.create(
            action="Role Changed",
            description=f"{request.user.username} changed {member.user.username} from {old_role} to {new_role}.",
            performed_by=request.user,
        )
        messages.success(request, f"{member.user.username}'s role updated to {new_role}.")
    else:
        messages.error(request, "Invalid role.")

    return redirect("accounts:settings")


# ── DEACTIVATE / ACTIVATE USER ────────────────────────────

@role_required("ADMIN")
def deactivate_user(request, member_id):
    if request.method != "POST":
        return redirect("accounts:settings")

    org    = get_org_user(request).organisation
    member = get_object_or_404(OrganisationUser, id=member_id, organisation=org)

    if member.user == request.user:
        messages.error(request, "You cannot deactivate yourself.")
        return redirect("accounts:settings")

    member.user.is_active = not member.user.is_active
    member.user.save()

    action = "activated" if member.user.is_active else "deactivated"
    AuditLog.objects.create(
        action=f"User {action.title()}",
        description=f"{request.user.username} {action} {member.user.username}.",
        performed_by=request.user,
    )
    messages.success(request, f"{member.user.username} has been {action}.")
    return redirect("accounts:settings")


# ── CANCEL INVITE ─────────────────────────────────────────

@role_required("ADMIN")
def cancel_invite(request, invite_id):
    if request.method != "POST":
        return redirect("accounts:settings")

    org    = get_org_user(request).organisation
    invite = get_object_or_404(UserInvite, id=invite_id, organisation=org)
    email  = invite.email
    invite.delete()
    messages.success(request, f"Invite to {email} cancelled.")
    return redirect("accounts:settings")


# ── SAVE PREFERENCES ─────────────────────────────────────

@login_required
def save_preferences(request):
    if request.method != "POST":
        return redirect("accounts:settings")

    org_user = get_org_user(request)
    action   = request.POST.get("action")

    if action == "save_theme":
        theme = request.POST.get("theme", "light")
        if theme in ("light", "dark"):
            org_user.theme = theme
            org_user.save(update_fields=["theme"])
            messages.success(request, "Theme updated.")

    elif action == "save_notifications":
        org_user.notify_payroll_complete = "notify_payroll_complete" in request.POST
        org_user.notify_salary_hold      = "notify_salary_hold"      in request.POST
        org_user.notify_salary_failed    = "notify_salary_failed"    in request.POST
        org_user.notify_approval_request = "notify_approval_request" in request.POST
        org_user.save(update_fields=[
            "notify_payroll_complete", "notify_salary_hold",
            "notify_salary_failed",    "notify_approval_request",
        ])
        messages.success(request, "Notification preferences saved.")

    return redirect("accounts:settings")