import pandas as pd
from django.shortcuts import render, redirect
from django.contrib import messages

from companies.models import Company
from employees.models import Employee
from banking.models import EmployeeBankAccount
from payroll.models import SalaryBatch, SalaryTransaction
from payroll.forms import SalaryUploadForm
from payroll.utils import should_hold_salary


def upload_salary(request):
    if request.method == "POST":
        form = SalaryUploadForm(request.POST, request.FILES)

        if form.is_valid():
            month = form.cleaned_data["month"]
            year = form.cleaned_data["year"]
            file = request.FILES["file"]

            company = Company.objects.first()

            batch, _ = SalaryBatch.objects.get_or_create(
                company=company,
                month=month,
                year=year
            )

            df = pd.read_excel(file)

            for _, row in df.iterrows():
                emp_code = str(row["emp_code"]).strip()
                salary_amount = row["salary"]

                try:
                    employee = Employee.objects.get(
                        emp_code=emp_code,
                        company=company
                    )
                except Employee.DoesNotExist:
                    continue  # skip invalid employee

                hold, reason = should_hold_salary(employee)

                bank = EmployeeBankAccount.objects.filter(
                    employee=employee,
                    is_active=True
                ).first()

                SalaryTransaction.objects.update_or_create(
                    batch=batch,
                    employee=employee,
                    defaults={
                        "salary_amount": salary_amount,
                        "account_number": bank.account_number if bank else None,
                        "ifsc": bank.ifsc if bank else None,
                        "status": "HOLD" if hold else "PENDING",
                        "hold_reason": reason,
                    }
                )

            messages.success(request, "Salary uploaded successfully")
            return redirect("salary_dashboard")

    else:
        form = SalaryUploadForm()

    return render(request, "payroll/upload.html", {"form": form})
