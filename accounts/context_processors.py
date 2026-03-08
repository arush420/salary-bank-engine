from .permissions import get_all_perms, get_user_role


def user_permissions(request):
    """
    Injects `perms` dict and `user_role` string into every template.

    Template usage:
        {% if perms.can_upload_payroll %}...{% endif %}
        {% if user_role == "ADMIN" %}...{% endif %}
    """
    if not request.user.is_authenticated:
        return {"perms": {}, "user_role": None}

    return {
        "perms": get_all_perms(request.user),
        "user_role": get_user_role(request.user),
    }