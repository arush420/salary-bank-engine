from employees.models import EmployeeDraft, EmployeeChangeRequest
from banking.models import BankChangeRequest

def approval_badges(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        return {}

    return {
        "approval_badges": {
            "employee_drafts": EmployeeDraft.objects.filter(status="PENDING").count(),
            "employee_changes": EmployeeChangeRequest.objects.filter(status="PENDING").count(),
            "bank_changes": BankChangeRequest.objects.filter(status="PENDING").count(),
        }
    }
