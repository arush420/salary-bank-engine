from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.timezone import now
from django.db import transaction

import pandas as pd

from payroll.models import SalaryBatch, SalaryTransaction
from companies.models import Company
from .forms import BankResponseUploadForm
from .models import BankChangeRequest
from banking.models import EmployeeBankAccount
from payroll.utils import release_salary_holds

# ---------------------------
# BANK CHANGE APPROVAL
# ---------------------------

def approval_queue(request):
    requests = BankChangeRequest.objects.filter(status="PENDING")
    return render(request, "banking/approval_queue.html", {"requests": requests})


def approve_request(request, id):
    req = get_object_or_404(BankChangeRequest, id=id)

    if req.status != "PENDING":
        return redirect("approval_queue")

    with transaction.atomic():
        EmployeeBankAccount.objects.filter(
            employee=req.employee,
            is_active=True
        ).update(is_active=False)

        EmployeeBankAccount.objects.create(
            employee=req.employee,
            bank_name=req.new_bank_name,
            account_number=req.new_account_number,
            ifsc=req.new_ifsc,
            effective_from_month=req.effective_from_month,
            is_active=True,
            approved_by=None,  # auth disabled for now
            approved_at=now()
        )

        req.status = "APPROVED"
        req.approved_at = now()
        req.save(update_fields=["status", "approved_at"])

        release_salary_holds(req.employee)

    return redirect("approval_queue")


# ---------------------------
# BANK RESPONSE (UTR) UPLOAD
# ---------------------------

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

                # ✅ AUTO COMPLETE BATCH
                pending_exists = SalaryTransaction.objects.filter(
                    batch=batch,
                    status="PENDING"
                ).exists()

                if not pending_exists:
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

# ---------------------------
# Retry Failed BANK Transactions
# ---------------------------
def retry_failed_transactions(request, batch_id):
    batch = get_object_or_404(SalaryBatch, id=batch_id)

    # 🔒 HARD BLOCKS
    if batch.status == "REVERSED":
        messages.error(
            request,
            "This batch was reversed and cannot be retried."
        )
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
        messages.info(
            request,
            "No failed transactions found to retry."
        )
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

        # Re-open batch for bank export
        batch.status = "EXPORTED"
        batch.save(update_fields=["status"])

    messages.success(
        request,
        "Failed transactions prepared for retry. Please export bank file again."
    )

    return redirect("dashboard:salary_dashboard")

# ---------------------------
# BANK Account Export File
# ---------------------------


def export_bank_file(request, month, year):
    # TODO: replace with request.user.company
    company = Company.objects.first()

    batch = get_object_or_404(
        SalaryBatch,
        company=company,
        month=month,
        year=year
    )

    # 🔒 HARD BLOCK — reversed batch
    if batch.status == "REVERSED":
        raise PermissionDenied("Reversed batch cannot be exported")

    # 🔒 BLOCK duplicate exports
    if batch.status != "DRAFT":
        raise PermissionDenied("Batch already exported or closed")

    # ✅ Export + lock atomically
    with transaction.atomic():
        # (Here you will generate CSV / Excel file)
        # generate_bank_file(batch)

        batch.status = "EXPORTED"
        batch.save(update_fields=["status"])

    return HttpResponse(
        f"Bank export completed for {month}/{year}",
        content_type="text/plain"
    )