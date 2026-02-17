import pandas as pd
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction

from companies.models import Company
from employees.models import Employee
from banking.models import EmployeeBankAccount
from payroll.models import SalaryBatch, SalaryTransaction
from payroll.forms import SalaryUploadForm
from payroll.utils import should_hold_salary


@login_required
def upload_salary(request):

    organisation = request.user.organisation_user.organisation

    companies = Company.objects.filter(
        organisation=organisation
    ).order_by("name")

    if request.method == "POST":

        form = SalaryUploadForm(request.POST, request.FILES)

        company_id = request.POST.get("company_id")

        # -----------------------------
        # Validate Company Selection
        # -----------------------------
        if not company_id:
            messages.error(request, "Please select a company.")
            return redirect("payroll:salary_upload")

        company = get_object_or_404(
            Company,
            id=company_id,
            organisation=organisation
        )

        # -----------------------------
        # Validate Form
        # -----------------------------
        if not form.is_valid():
            messages.error(request, "Invalid form submission.")
            return redirect("payroll:salary_upload")

        month = form.cleaned_data["month"]
        year = form.cleaned_data["year"]
        file = form.cleaned_data["file"]

        # -----------------------------
        # Get or Create Batch
        # -----------------------------
        batch, _ = SalaryBatch.objects.get_or_create(
            company=company,
            month=month,
            year=year,
        )

        # -----------------------------
        # Hard Lock Checks
        # -----------------------------
        if batch.status == "REVERSED":
            messages.error(request, "This batch was reversed and is permanently locked.")
            return redirect("payroll:batch_detail", batch_id=batch.id)

        if batch.status != "DRAFT":
            messages.error(request, "Only DRAFT batches can be modified.")
            return redirect("payroll:batch_detail", batch_id=batch.id)

        # -----------------------------
        # Read Excel File
        # -----------------------------
        try:
            df = pd.read_excel(file)
        except Exception:
            messages.error(request, "Invalid or corrupted Excel file.")
            return redirect("payroll:salary_upload")

        # -----------------------------
        # Validate Required Columns
        # -----------------------------
        required_columns = {"site_code", "emp_code", "emp_name", "salary"}

        if not required_columns.issubset(df.columns):
            messages.error(
                request,
                f"Excel must contain columns: {', '.join(sorted(required_columns))}"
            )
            return redirect("payroll:salary_upload")

        created = 0
        updated = 0
        skipped = 0

        # -----------------------------
        # Process Rows
        # -----------------------------
        with transaction.atomic():

            for _, row in df.iterrows():

                emp_code = str(row.get("emp_code", "")).strip()
                site_code = row.get("site_code")
                salary_amount = row.get("salary")

                # Skip invalid salary
                if pd.isna(salary_amount) or salary_amount <= 0:
                    skipped += 1
                    continue

                # Optional: Validate site_code
                if hasattr(company, "site_code") and site_code != company.site_code:
                    skipped += 1
                    continue

                # Validate employee
                try:
                    employee = Employee.objects.get(
                        emp_code=emp_code,
                        company=company
                    )
                except Employee.DoesNotExist:
                    skipped += 1
                    continue

                # Salary Hold Logic
                hold, reason = should_hold_salary(employee)

                bank = EmployeeBankAccount.objects.filter(
                    employee=employee,
                    is_active=True
                ).first()

                txn, created_flag = SalaryTransaction.objects.update_or_create(
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

                if created_flag:
                    created += 1
                else:
                    updated += 1

        # -----------------------------
        # Final Success Message
        # -----------------------------
        messages.success(
            request,
            f"Upload completed successfully — "
            f"Created: {created}, Updated: {updated}, Skipped: {skipped}"
        )

        return redirect("payroll:batch_detail", batch_id=batch.id)

    else:
        form = SalaryUploadForm()

    return render(
        request,
        "payroll/upload.html",
        {
            "form": form,
            "companies": companies,
        }
    )


@login_required
def download_salary_template(request, company_id):

    company = get_object_or_404(Company, id=company_id)

    employees = Employee.objects.filter(
        company=company,
        exit_date__isnull=True   # only active employees
    ).order_by("emp_code")

    data = []

    for emp in employees:
        data.append({
            "site_code": company.site_code if hasattr(company, "site_code") else "",
            "emp_code": emp.emp_code,
            "emp_name": emp.name,
            "salary": ""
        })

    df = pd.DataFrame(data)

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    filename = f"{company.name}_salary_template.xlsx"
    response["Content-Disposition"] = f"attachment; filename={filename}"

    df.to_excel(response, index=False)

    return response



@login_required
def salary_batch_list(request):
    company = request.user.organisation_user.organisation.company

    batches = SalaryBatch.objects.filter(
        company=company
    ).prefetch_related("transactions")

    return render(
        request,
        "payroll/batch_list.html",
        {"batches": batches}
    )

@login_required
def salary_batch_detail(request, batch_id):
    batch = get_object_or_404(SalaryBatch, id=batch_id)

    transactions = batch.transactions.select_related("employee")
    summary = {
        "total": transactions.count(),
        "pending": transactions.filter(status="PENDING").count(),
        "hold": transactions.filter(status="HOLD").count(),
        "processed": transactions.filter(status="PROCESSED").count(),
        "failed": transactions.filter(status="FAILED").count(),
    }

    return render(
        request,
        "payroll/batch_detail.html",
        {
            "batch": batch,
            "transactions": transactions,
            "summary": summary,
        }
    )


@login_required
def finalize_batch(request, batch_id):
    batch = get_object_or_404(SalaryBatch, id=batch_id)

    if batch.status != "DRAFT":
        messages.error(request, "Only draft batches can be finalized.")
        return redirect("payroll:batch_detail", batch_id=batch.id)

    # Validation before finalize
    if batch.transactions.count() == 0:
        messages.error(request, "Cannot finalize empty batch.")
        return redirect("payroll:batch_detail", batch.id)

    if batch.transactions.filter(status="HOLD").exists():
        messages.error(request, "Resolve HOLD transactions before finalizing.")
        return redirect("payroll:batch_detail", batch.id)

    batch.status = "READY"
    batch.save(update_fields=["status"])

    messages.success(request, "Batch finalized successfully.")
    return redirect("payroll:batch_detail", batch.id)

@login_required
def export_batch(request, batch_id):
    batch = get_object_or_404(SalaryBatch, id=batch_id)

    if batch.status != "READY":
        messages.error(request, "Only READY batches can be exported.")
        return redirect("payroll:batch_detail", batch.id)

    # Final validation
    if batch.transactions.filter(account_number__isnull=True).exists():
        messages.error(request, "Some employees do not have bank accounts.")
        return redirect("payroll:batch_detail", batch.id)

    batch.status = "EXPORTED"
    batch.save(update_fields=["status"])

    messages.success(request, "Batch exported successfully.")
    return redirect("payroll:batch_detail", batch.id)
