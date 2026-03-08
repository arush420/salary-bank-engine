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
        # Read & Validate Excel FIRST ← moved up
        # -----------------------------
        try:
            df = pd.read_excel(file)
        except Exception:
            messages.error(request, "Invalid or corrupted Excel file.")
            return redirect("payroll:salary_upload")

        required_columns = {"site_code", "emp_code", "emp_name", "salary"}
        if not required_columns.issubset(df.columns):
            messages.error(
                request,
                f"Excel must contain columns: {', '.join(sorted(required_columns))}"
            )
            return redirect("payroll:salary_upload")

        # -----------------------------
        # Get or Create Batch ← moved down, only runs if file is valid
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

                if pd.isna(salary_amount) or salary_amount <= 0:
                    skipped += 1
                    continue

                if hasattr(company, "site_code") and site_code != company.site_code:
                    skipped += 1
                    continue

                try:
                    employee = Employee.objects.get(
                        emp_code=emp_code,
                        company=company
                    )
                except Employee.DoesNotExist:
                    skipped += 1
                    continue

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

    organisation = request.user.organisation_user.organisation
    company = get_object_or_404(Company, id=company_id, organisation=organisation)

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
    organisation = request.user.organisation_user.organisation

    batches = SalaryBatch.objects.filter(
        company__organisation=organisation
    ).prefetch_related("transactions").order_by("-year", "-month")

    return render(request, "payroll/batch_list.html", {"batches": batches})


@login_required
def salary_batch_detail(request, batch_id):
    organisation = request.user.organisation_user.organisation
    batch = get_object_or_404(
        SalaryBatch,
        id=batch_id,
        company__organisation=organisation
    )

    transactions = batch.transactions.select_related("employee")
    summary = {
        "total": transactions.count(),
        "pending": transactions.filter(status="PENDING").count(),
        "hold": transactions.filter(status="HOLD").count(),
        "processed": transactions.filter(status="PROCESSED").count(),
        "failed": transactions.filter(status="FAILED").count(),
        "exported": transactions.filter(status="EXPORTED").count(),
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


@perm_required("can_upload_payroll")
def finalize_batch(request, batch_id):
    batch = get_object_or_404(SalaryBatch, id=batch_id)

    if batch.status != "DRAFT":
        messages.error(request, "Only draft batches can be finalized.")
        return redirect("payroll:batch_detail", batch_id=batch.id)

    if batch.transactions.count() == 0:
        messages.error(request, "Cannot finalize an empty batch.")
        return redirect("payroll:batch_detail", batch_id=batch.id)

    if batch.transactions.filter(status="HOLD").exists():
        messages.error(request, "Resolve all HOLD transactions before finalizing.")
        return redirect("payroll:batch_detail", batch_id=batch.id)

    if batch.transactions.filter(account_number__isnull=True).exists():
        messages.error(request, "Some employees are missing bank account details.")
        return redirect("payroll:batch_detail", batch_id=batch.id)

    with transaction.atomic():
        batch.transactions.filter(status="PENDING").update(status="EXPORTED")
        batch.status = "EXPORTED"
        batch.save(update_fields=["status"])

    messages.success(request, "Batch finalized and marked as exported.")
    return redirect("payroll:batch_detail", batch_id=batch.id)

@login_required
def export_batch(request, batch_id):
    batch = get_object_or_404(SalaryBatch, id=batch_id)

    if batch.status != "EXPORTED":
        messages.error(request, "Only exported batches can generate a bank file.")
        return redirect("payroll:batch_detail", batch_id=batch.id)

    transactions = batch.transactions.filter(
        status="EXPORTED"
    ).select_related("employee")

    rows = [
        {
            "Emp Code": txn.employee.emp_code,
            "Employee Name": txn.employee.name,
            "Account Number": txn.account_number,
            "IFSC": txn.ifsc,
            "Salary": txn.salary_amount,
        }
        for txn in transactions
    ]

    df = pd.DataFrame(rows)
    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = f'attachment; filename="bank_file_{batch.month}_{batch.year}.xlsx"'
    df.to_excel(response, index=False)
    return response