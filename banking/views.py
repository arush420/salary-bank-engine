from django.shortcuts import render, redirect
# from django.contrib.auth.decorators import user_passes_test
from employees.models import BankChangeRequest, EmployeeBankAccount
from django.utils.timezone import now

def is_approver(user):
    return user.groups.filter(name__in=["ADMIN", "BANK_APPROVER"]).exists()

# @user_passes_test(is_approver)
def approval_queue(request):
    requests = BankChangeRequest.objects.filter(status="PENDING")
    return render(request, "banking/approval_queue.html", {"requests": requests})


# @user_passes_test(is_approver)
def approve_request(request, id):
    req = BankChangeRequest.objects.get(id=id)

    EmployeeBankAccount.objects.filter(employee=req.employee, is_active=True).update(is_active=False)

    EmployeeBankAccount.objects.create(
        employee=req.employee,
        bank_name=req.new_bank_name,
        account_number=req.new_account_number,
        ifsc=req.new_ifsc,
        effective_from_month=req.effective_from_month,
        is_active=True,
        approved_by=request.user,
        approved_at=now()
    )

    req.status = "APPROVED"
    req.approved_by = request.user
    req.approved_at = now()
    req.save()

    return redirect("approval_queue")
