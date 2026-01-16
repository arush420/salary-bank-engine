from django.shortcuts import render, redirect
from django.utils.timezone import now
from django.db import transaction

import pandas as pd

from employees.models import BankChangeRequest, EmployeeBankAccount
from payroll.models import SalaryBatch, SalaryTransaction
from companies.models import Company
from .forms import BankResponseUploadForm


# ---------------------------
# BANK CHANGE APPROVAL
# ---------------------------

def approval_queue(request):
    requests = BankChangeRequest.objects.filter(status="PENDING")
    return render(request, "banking/approval_queue.html", {"requests": requests})


def approve_request(request, id):
    req = BankChangeRequest.objects.get(id=id)

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
            approved_by=None,   # auth disabled for now
            approved_at=now()
        )

        req.status = "APPROVED"
        req.approved_at = now()
        req.save()

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
            file = form.cleaned_data["file"]

            company = Company.objects.first()
            batch = SalaryBatch.objects.get(
                company=company,
                month=month,
                year=year
            )

            # --- Read file using pandas (CSV + Excel)
            if file.name.lower().endswith(".csv"):
                df = pd.read_csv(file)
            else:
                df = pd.read_excel(file)

            # Normalize column names
            df.columns = df.columns.str.strip()

            # Fetch all pending transactions once
            pending_txns = {
                (str(t.account_number), float(t.salary_amount)): t
                for t in SalaryTransaction.objects.filter(
                    batch=batch,
                    status="PENDING"
                )
            }

            updated_txns = []

            for _, row in df.iterrows():
                account = str(row["AccountNumber"]).strip()
                amount = float(row["Amount"])
                status = str(row["Status"]).upper().strip()
                utr = str(row.get("UTR", "")).strip()

                txn = pending_txns.get((account, amount))
                if not txn:
                    continue

                txn.bank_response_at = now()

                if status == "SUCCESS":
                    txn.status = "PROCESSED"
                    txn.utr = utr
                else:
                    txn.status = "FAILED"

                updated_txns.append(txn)

            # Bulk update (FAST & SAFE)
            SalaryTransaction.objects.bulk_update(
                updated_txns,
                ["status", "utr", "bank_response_at"]
            )

            return redirect("/bank/response-upload/")

    else:
        form = BankResponseUploadForm()

    return render(
        request,
        "banking/bank_response_upload.html",
        {"form": form}
    )
