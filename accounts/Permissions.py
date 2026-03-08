"""
Central permissions map for Salary Engine.

Usage in views:
    from accounts.permissions import role_required
    @role_required("ADMIN", "MANAGER")
    def my_view(request): ...

Usage in templates (via context processor):
    {% if perms.can_upload_payroll %}...{% endif %}
"""

from functools import wraps
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


# ── PERMISSION MAP ────────────────────────────────────────
# Each key is a permission name used in templates and views.
# Values are the roles that have that permission.

PERMISSIONS = {
    # Settings
    "can_access_settings":      ["ADMIN"],

    # Approvals
    "can_approve_drafts":       ["ADMIN", "MANAGER"],
    "can_approve_bank_changes": ["ADMIN", "MANAGER"],

    # Payroll
    "can_upload_payroll":       ["ADMIN", "MANAGER"],
    "can_manage_transactions":  ["ADMIN", "MANAGER"],

    # Banking
    "can_upload_bank_utr":      ["ADMIN", "MANAGER"],

    # Employees
    "can_add_employee":         ["ADMIN", "MANAGER", "SUPERVISOR"],
    "can_view_employees":       ["ADMIN", "MANAGER", "SUPERVISOR"],

    # Reports
    "can_view_reports":         ["ADMIN", "MANAGER", "SUPERVISOR"],
    "can_download_reports":     ["ADMIN", "MANAGER"],

    # Companies
    "can_manage_companies":     ["ADMIN"],
}


# ── HELPER ────────────────────────────────────────────────

def get_user_role(user):
    """Returns role string or None."""
    try:
        return user.organisation_user.role
    except Exception:
        return None


def user_has_perm(user, perm_name):
    """Check if a user has a given permission."""
    role = get_user_role(user)
    if not role:
        return False
    allowed_roles = PERMISSIONS.get(perm_name, [])
    return role in allowed_roles


def get_all_perms(user):
    """Returns a dict of all permission booleans for a user — injected into templates."""
    return {perm: user_has_perm(user, perm) for perm in PERMISSIONS}


# ── DECORATOR ─────────────────────────────────────────────

def role_required(*allowed_roles):
    """
    View decorator. Usage:
        @role_required("ADMIN", "MANAGER")
        def my_view(request): ...
    """
    def decorator(view_fn):
        @wraps(view_fn)
        @login_required
        def wrapper(request, *args, **kwargs):
            role = get_user_role(request.user)
            if role not in allowed_roles:
                messages.error(request, "You don't have permission to access this page.")
                return redirect("dashboard:home")
            return view_fn(request, *args, **kwargs)
        return wrapper
    return decorator


def perm_required(perm_name):
    """
    Permission-based decorator. Usage:
        @perm_required("can_upload_payroll")
        def my_view(request): ...
    """
    def decorator(view_fn):
        @wraps(view_fn)
        @login_required
        def wrapper(request, *args, **kwargs):
            if not user_has_perm(request.user, perm_name):
                messages.error(request, "You don't have permission to access this page.")
                return redirect("dashboard:home")
            return view_fn(request, *args, **kwargs)
        return wrapper
    return decorator