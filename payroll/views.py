import csv
import io

import openpyxl
import pandas as pd
from django.shortcuts import render, redirect

from banking.models import EmployeeBankAccount
from .models import SalaryBatch, SalaryTransaction
from .forms import SalaryUploadForm
from companies.models import Company
from employees.models import Employee

def upload_salary(request):
    if request.method == "POST":
        form = SalaryUploadForm(request.POST, request.FILES)
        if form.is_valid():
            month = form.cleaned_data["month"]
            year = form.cleaned_data["year"]
            file = request.FILES["file"]

            company = Company.objects.first()

            batch, created = SalaryBatch.objects.get_or_create(
                company=company, month=month, year=year
            )

            wb = openpyxl.load_workbook(file)
            sheet = wb.active

            for row in sheet.iter_rows(min_row=2, values_only=True):
                emp_code, name, salary, hold = row

                employee = Employee.objects.get(emp_code=emp_code, company=company)
                bank = EmployeeBankAccount.objects.get(employee=employee, is_active=True)

                status = "HOLD" if str(hold).lower() == "yes" else "PENDING"

                SalaryTransaction.objects.create(
                    batch=batch,
                    employee=employee,
                    salary_amount=salary,
                    account_number=bank.account_number,
                    ifsc=bank.ifsc,
                    status=status
                )

            return redirect("salary_list")

    else:
        form = SalaryUploadForm()

    return render(request, "payroll/upload.html", {"form": form})
