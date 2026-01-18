from django.shortcuts import render, redirect

from payroll.models import SalaryTransaction
# from django.contrib.auth.decorators import login_required
from .forms import BankChangeRequestForm
from .models import Employee
from banking.models import EmployeeBankAccount, BankChangeRequest



# @login_required
def request_bank_change(request):
    employee = Employee.objects.first()

    if request.method == "POST":
        form = BankChangeRequestForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.employee = employee
            obj.submitted_by = request.user
            obj.save()
            return redirect("bank_request_success")
    else:
        form = BankChangeRequestForm()

    return render(request, "employees/bank_request.html", {"form": form})

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
