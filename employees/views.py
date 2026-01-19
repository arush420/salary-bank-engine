from django.shortcuts import render, redirect

from payroll.models import SalaryTransaction
# from django.contrib.auth.decorators import login_required
from .forms import BankChangeRequestForm
from .models import Employee
from banking.models import EmployeeBankAccount, BankChangeRequest



# @login_required
def request_bank_change(request, employee_id):
    if request.method == "POST":
        form = BankChangeRequestForm(request.POST)
        if form.is_valid():
            req = form.save(commit=False)
            req.employee_id = employee_id
            req.save()
            return redirect("employees:employee_profile", employee_id=employee_id)
    else:
        form = BankChangeRequestForm()

    return render(
        request,
        "employees/request_bank_change.html",
        {"form": form}
    )

def employee_list(request):
    employees = Employee.objects.order_by("emp_code")
    return render(
        request,
        "employees/employee_list.html",
        {"employees": employees}
    )


def employee_profile(request, employee_id):
    employee = Employee.objects.get(id=employee_id)

    latest_salary = SalaryTransaction.objects.filter(
        employee=employee
    ).order_by(
        "-batch__year", "-batch__month"
    ).first()

    bank_accounts = EmployeeBankAccount.objects.filter(
        employee=employee
    ).order_by(
        "-is_active", "-approved_at"
    )

    active_account = bank_accounts.filter(is_active=True).first()

    context = {
        "employee": employee,
        "latest_salary": latest_salary,
        "bank_accounts": bank_accounts,
        "active_account": active_account,
    }

    return render(
        request,
        "employees/employee_profile.html",
        context
    )
