from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.timezone import now
from django.db import transaction
from datetime import date
import pandas as pd

from employees.models import Employee
from payroll.models import SalaryBatch, SalaryTransaction
from companies.models import Company
from .forms import BankResponseUploadForm
from .models import BankChangeRequest
from banking.models import EmployeeBankAccount
from payroll.utils import release_salary_holds


# =====================================================
# BANK CHANGE APPROVAL QUEUE
# =====================================================

def approval_queue(request):
    requests = BankChangeRequest.objects.filter(status="PENDING")
    return render(request, "banking/approval_queue.html", {"requests": requests})


# =====================================================
# APPROVE BANK CHANGE REQUEST
# =====================================================

def approve_request(request, id):
    req = get_object_or_404(BankChangeRequest, id=id)

    if req.status != "PENDING":
        return redirect("banking:bank_change_approval_list")

    with transaction.atomic():

        # Deactivate old active account
        EmployeeBankAccount.objects.filter(
            employee=req.employee,
            is_active=True
        ).update(is_active=False)

        # Convert month/year → first day of month
        effective_date = date(
            req.effective_year,
            req.effective_month,
            1
        )

        # Create new bank account
        EmployeeBankAccount.objects.create(
            employee=req.employee,
            bank_name=req.new_bank_name,
            account_number=req.new_account_number,
            ifsc=req.new_ifsc,
            effective_from_month=effective_date,
            is_active=True,
            approved_by=request.user,
            approved_at=now()
        )

        # Update request status
        req.status = "APPROVED"
        req.approved_by = request.user
        req.approved_at = now()
        req.save(update_fields=["status", "approved_by", "approved_at"])

        # Release salary holds
        release_salary_holds(req.employee)

    messages.success(request, "Bank change approved successfully.")
    return redirect("banking:bank_change_approval_list")

# =====================================================
# DOWNLOAD BANK Template
# =====================================================
@login_required
def download_bank_template(request, company_id):

    organisation = request.user.organisation_user.organisation

    company = get_object_or_404(
        Company,
        id=company_id,
        organisation=organisation
    )

    # Employees without active bank
    employees = Employee.objects.filter(
        company=company
    ).exclude(
        bank_accounts__is_active=True
    )

    data = []

    for emp in employees:
        data.append({
            "Site Code": company.site_code,
            "Emp Code": emp.emp_code,
            "Employee Name": emp.name,
            "Account Number": "",
            "IFSC": "",
        })

    df = pd.DataFrame(data)

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    filename = f"{company.name}_bank_template.xlsx"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    df.to_excel(response, index=False)

    return response
# =====================================================
# BANK Account Bulk Upload
# =====================================================
from datetime import date
from django.db.models import Q

@login_required
def bulk_bank_upload(request):

    companies = Company.objects.filter(
        organisation=request.user.organisation_user.organisation
    )

    if request.method == "POST":

        company_id = request.POST.get("company_id")
        file = request.FILES.get("file")

        if not company_id or not file:
            messages.error(request, "Company and file required.")
            return redirect("banking:bulk_bank_upload")

        company = get_object_or_404(
            Company,
            id=company_id,
            organisation=request.user.organisation_user.organisation
        )

        try:
            df = pd.read_excel(file)
        except Exception:
            messages.error(request, "Invalid Excel file.")
            return redirect("banking:bulk_bank_upload")

        required_cols = {"Emp Code", "Account Number", "IFSC"}

        if not required_cols.issubset(df.columns):
            messages.error(request, "Invalid template format.")
            return redirect("banking:bulk_bank_upload")

        created = 0
        skipped = 0

        # 👇 Effective date = current month first day
        today = date.today()
        effective_date = date(today.year, today.month, 1)

        with transaction.atomic():

            for _, row in df.iterrows():

                emp_code = str(row["Emp Code"]).strip()
                account_number = str(row["Account Number"]).strip()
                ifsc = str(row["IFSC"]).strip().upper()

                # Basic validation
                if not emp_code or not account_number or not ifsc:
                    skipped += 1
                    continue

                # IFSC length validation
                if len(ifsc) != 11:
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

                # Deactivate old active accounts (enterprise-safe)
                EmployeeBankAccount.objects.filter(
                    employee=employee,
                    is_active=True
                ).update(is_active=False)

                # Create new account
                EmployeeBankAccount.objects.create(
                    employee=employee,
                    bank_name="Bulk Upload",
                    account_number=account_number,
                    ifsc=ifsc,
                    effective_from_month=effective_date,
                    is_active=True
                )

                release_salary_holds(employee)

                created += 1

        messages.success(
            request,
            f"Upload complete — Created: {created}, Skipped: {skipped}"
        )

        return redirect("banking:bulk_bank_upload")

    return render(
        request,
        "banking/bulk_bank_upload.html",
        {"companies": companies}
    )

# =====================================================
# BANK RESPONSE (UTR) UPLOAD
# =====================================================

def upload_bank_response(request):
    if request.method == "POST":
        form = BankResponseUploadForm(request.POST, request.FILES)

        if form.is_valid():
            month = form.cleaned_data["month"]
            year = form.cleaned_data["year"]
            file = request.FILES["file"]

            batch = SalaryBatch.objects.filter(
                month=month,
                year=year,
                status="EXPORTED"
            ).first()

            if not batch:
                messages.error(
                    request,
                    "No exported salary batch found for selected month/year."
                )
                return redirect("banking:bank_response_upload")

            df = pd.read_excel(file)

            required_columns = {"emp_code", "status"}
            if not required_columns.issubset(df.columns):
                messages.error(
                    request,
                    "Bank response must contain emp_code and status columns."
                )
                return redirect("banking:bank_response_upload")

            with transaction.atomic():
                for _, row in df.iterrows():
                    emp_code = str(row["emp_code"]).strip()
                    status = str(row["status"]).upper().strip()
                    utr = str(row.get("utr", "")).strip()
                    reason = str(row.get("reason", "")).strip()

                    txn = SalaryTransaction.objects.filter(
                        batch=batch,
                        employee__emp_code=emp_code,
                        status="PENDING"
                    ).first()

                    if not txn:
                        continue

                    if status == "SUCCESS":
                        txn.status = "PROCESSED"
                        txn.utr = utr
                        txn.failure_reason = None

                    elif status == "FAILED":
                        txn.status = "FAILED"
                        txn.failure_reason = reason or "Bank processing failed"

                    else:
                        continue

                    txn.bank_response_at = now()
                    txn.save()

                # Auto-complete batch if no pending transactions
                if not SalaryTransaction.objects.filter(
                    batch=batch,
                    status="PENDING"
                ).exists():
                    batch.status = "COMPLETED"
                    batch.save(update_fields=["status"])

            messages.success(request, "Bank response processed successfully.")
            return redirect("dashboard:salary_dashboard")

    else:
        form = BankResponseUploadForm()

    return render(
        request,
        "banking/bank_response_upload.html",
        {"form": form}
    )


# =====================================================
# RETRY FAILED TRANSACTIONS
# =====================================================

def retry_failed_transactions(request, batch_id):
    batch = get_object_or_404(SalaryBatch, id=batch_id)

    if batch.status == "REVERSED":
        messages.error(request, "This batch was reversed and cannot be retried.")
        return redirect("dashboard:salary_dashboard")

    if batch.status not in ["EXPORTED", "COMPLETED"]:
        messages.error(
            request,
            "Retry is allowed only for exported or completed batches."
        )
        return redirect("dashboard:salary_dashboard")

    failed_txns = SalaryTransaction.objects.filter(
        batch=batch,
        status="FAILED"
    )

    if not failed_txns.exists():
        messages.info(request, "No failed transactions found to retry.")
        return redirect("dashboard:salary_dashboard")

    with transaction.atomic():
        for txn in failed_txns:
            SalaryTransaction.objects.create(
                batch=batch,
                employee=txn.employee,
                salary_amount=txn.salary_amount,
                account_number=txn.account_number,
                ifsc=txn.ifsc,
                status="PENDING",
            )

        batch.status = "EXPORTED"
        batch.save(update_fields=["status"])

    messages.success(
        request,
        "Failed transactions prepared for retry. Please export bank file again."
    )

    return redirect("dashboard:salary_dashboard")


# =====================================================
# EXPORT BANK FILE
# =====================================================

def export_bank_file(request, month, year):

    company = request.user.organisation_user.organisation.company

    batch = get_object_or_404(
        SalaryBatch,
        company=company,
        month=month,
        year=year
    )

    # 🔒 Reversed check
    if batch.status == "REVERSED":
        raise PermissionDenied("Reversed batch cannot be exported")

    # 🔒 Only Draft allowed
    if batch.status != "DRAFT":
        raise PermissionDenied("Batch already exported or closed")

    # ============================
    # 🔥 STEP 4 VALIDATION HERE
    # ============================

    # 1️⃣ No HOLD transactions
    if batch.transactions.filter(status="HOLD").exists():
        messages.error(request, "Cannot export: Some salaries are on HOLD.")
        return redirect("payroll:batch_detail", batch.id)

    # 2️⃣ All transactions must have bank data
    if batch.transactions.filter(account_number__isnull=True).exists():
        messages.error(request, "Cannot export: Some employees have no bank account.")
        return redirect("payroll:batch_detail", batch.id)

    # 3️⃣ No negative salary
    if batch.transactions.filter(salary_amount__lte=0).exists():
        messages.error(request, "Invalid salary amounts detected.")
        return redirect("payroll:batch_detail", batch.id)

    # ============================

    with transaction.atomic():
        batch.status = "EXPORTED"
        batch.save(update_fields=["status"])

    messages.success(request, f"Bank export completed for {month}/{year}")

    return redirect("dashboard:salary_dashboard")
