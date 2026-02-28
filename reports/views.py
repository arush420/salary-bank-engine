from datetime import date
import pandas as pd
from django.contrib import messages

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Sum, Count
from django.urls import reverse

from companies.models import Company
from payroll.models import SalaryBatch, SalaryTransaction
from banking.models import BankChangeRequest, EmployeeBankAccount


# =====================================================
# REPORTS DASHBOARD
# =====================================================

@login_required
def reports_dashboard(request):
    return render(request, "reports/dashboard.html")


# =====================================================
# SALARY REPORT
# =====================================================

@login_required
def salary_report(request):
    today = date.today()

    month = int(request.GET.get("month", today.month))
    year = int(request.GET.get("year", today.year))
    company_id = request.GET.get("company")
    export = request.GET.get("export")

    organisation = request.user.organisation_user.organisation

    companies = Company.objects.filter(organisation=organisation)

    selected_company = None
    transactions = SalaryTransaction.objects.none()

    # ---------------------------------------------
    # Load Transactions
    # ---------------------------------------------

    if company_id:
        selected_company = get_object_or_404(
            Company,
            id=company_id,
            organisation=organisation
        )

        batch = SalaryBatch.objects.filter(
            company=selected_company,
            month=month,
            year=year
        ).first()

        if batch:
            transactions = SalaryTransaction.objects.filter(
                batch=batch
            ).select_related("employee")

    # ---------------------------------------------
    # EXPORT TO EXCEL
    # ---------------------------------------------

    if export == "excel" and selected_company and transactions.exists():

        # ========== DETAIL DATA ==========
        detail_rows = [
            {
                "Site Code": selected_company.site_code,
                "Company": selected_company.name,
                "Emp Code": txn.employee.emp_code,
                "Employee Name": txn.employee.name,
                "Salary": txn.salary_amount,
                "Status": txn.status,
                "Account Number": txn.account_number,
                "IFSC": txn.ifsc,
            }
            for txn in transactions
        ]

        df_detail = pd.DataFrame(detail_rows)

        # ========== SUMMARY ==========
        summary = (
            df_detail
            .groupby("Status")["Salary"]
            .agg(["count", "sum"])
            .reset_index()
        )

        summary.rename(columns={
            "count": "Total Employees",
            "sum": "Total Salary"
        }, inplace=True)

        grand_total = pd.DataFrame([{
            "Status": "TOTAL",
            "Total Employees": summary["Total Employees"].sum(),
            "Total Salary": summary["Total Salary"].sum(),
        }])

        df_summary = pd.concat([summary, grand_total], ignore_index=True)

        # ========== RESPONSE ==========
        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        filename = f"{selected_company.name}_{month}_{year}_salary_report.xlsx"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        with pd.ExcelWriter(response, engine="openpyxl") as writer:
            df_detail.to_excel(writer, sheet_name="Salary Details", index=False)
            df_summary.to_excel(writer, sheet_name="Summary", index=False)

        return response

    # ---------------------------------------------
    # Render HTML View
    # ---------------------------------------------

    context = {
        "companies": companies,
        "selected_company": selected_company,
        "transactions": transactions,
        "month": month,
        "year": year,
        "months": range(1, 13),
        "years": range(today.year - 3, today.year + 2),
    }

    return render(request, "reports/salary_report.html", context)

from django.db.models import Sum, Count
from django.utils.timezone import now


@login_required
def yearly_salary_report(request):

    year = request.GET.get("year")
    company_id = request.GET.get("company")

    if not year or not company_id:
        return HttpResponse("Year and Company required")

    organisation = request.user.organisation_user.organisation

    company = get_object_or_404(
        Company,
        id=company_id,
        organisation=organisation
    )

    batches = SalaryBatch.objects.filter(
        company=company,
        year=year
    )

    transactions = SalaryTransaction.objects.filter(
        batch__in=batches
    ).select_related("employee", "batch")

    if not transactions.exists():
        return HttpResponse("No salary data for selected year")

    # ============================================
    # SHEET 1 — FULL TRANSACTION DATA
    # ============================================

    detail_rows = []

    for txn in transactions:
        detail_rows.append({
            "Month": txn.batch.month,
            "Emp Code": txn.employee.emp_code,
            "Employee Name": txn.employee.name,
            "Salary": txn.salary_amount,
            "Status": txn.status,
        })

    df_detail = pd.DataFrame(detail_rows)

    # ============================================
    # SHEET 2 — MONTHLY SUMMARY
    # ============================================

    monthly_summary = (
        df_detail
        .groupby(["Month", "Status"])["Salary"]
        .agg(["count", "sum"])
        .reset_index()
    )

    monthly_pivot = (
        monthly_summary
        .pivot_table(
            index="Month",
            columns="Status",
            values="sum",
            fill_value=0
        )
        .reset_index()
    )

    monthly_total = (
        df_detail
        .groupby("Month")["Salary"]
        .sum()
        .reset_index(name="Total Salary")
    )

    df_monthly = monthly_total.merge(monthly_pivot, on="Month", how="left")

    # ============================================
    # SHEET 3 — YEAR SUMMARY
    # ============================================

    year_summary = {
        "Total Transactions": len(df_detail),
        "Total Salary": df_detail["Salary"].sum(),
        "Processed Salary": df_detail[df_detail["Status"] == "PROCESSED"]["Salary"].sum(),
        "Hold Salary": df_detail[df_detail["Status"] == "HOLD"]["Salary"].sum(),
        "Failed Salary": df_detail[df_detail["Status"] == "FAILED"]["Salary"].sum(),
    }

    df_year_summary = pd.DataFrame([year_summary])

    # ============================================
    # EXPORT MULTI-SHEET EXCEL
    # ============================================

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    filename = f"{company.name}_{year}_yearly_salary_report.xlsx"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    with pd.ExcelWriter(response, engine="openpyxl") as writer:
        df_detail.to_excel(writer, sheet_name="Transactions", index=False)
        df_monthly.to_excel(writer, sheet_name="Monthly Summary", index=False)
        df_year_summary.to_excel(writer, sheet_name="Year Summary", index=False)

    return response

# =====================================================
# BANK CHANGE REPORT
# =====================================================

@login_required
def bank_change_report(request):

    organisation = request.user.organisation_user.organisation

    month = request.GET.get("month")
    year = request.GET.get("year")
    status = request.GET.get("status")

    qs = BankChangeRequest.objects.select_related(
        "employee",
        "submitted_by",
        "approved_by",
        "employee__company"
    ).filter(
        employee__company__organisation=organisation
    )

    if month:
        qs = qs.filter(effective_month=month)

    if year:
        qs = qs.filter(effective_year=year)

    if status and status != "ALL":
        qs = qs.filter(status=status)

    # ---------------------------------------------
    # Prepare Data
    # ---------------------------------------------

    rows = [
        {
            "Company": req.employee.company.name,
            "Emp Code": req.employee.emp_code,
            "Employee Name": req.employee.name,
            "New Bank": req.new_bank_name,
            "New Account": req.new_account_number,
            "IFSC": req.new_ifsc,
            "Effective Month": req.effective_month,
            "Effective Year": req.effective_year,
            "Status": req.status,
            "Submitted By": req.submitted_by.username,
            "Approved By": req.approved_by.username if req.approved_by else "",
        }
        for req in qs
    ]

    df = pd.DataFrame(rows)

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    response["Content-Disposition"] = "attachment; filename=bank_change_report.xlsx"

    df.to_excel(response, index=False)

    return response

@login_required
def transaction_status_manager(request):
    today = date.today()
    organisation = request.user.organisation_user.organisation

    month = int(request.GET.get("month", today.month))
    year = int(request.GET.get("year", today.year))
    company_id = request.GET.get("company")
    status_filter = request.GET.get("status", "ALL")

    companies = Company.objects.filter(organisation=organisation)
    selected_company = None
    transactions = SalaryTransaction.objects.none()

    # -----------------------------------------------
    # HANDLE POST — status change actions
    # -----------------------------------------------
    if request.method == "POST":
        action = request.POST.get("action")
        transaction_id = request.POST.get("transaction_id")
        hold_reason = request.POST.get("hold_reason", "").strip()

        txn = get_object_or_404(SalaryTransaction, id=transaction_id)

        if action == "hold":
            if not hold_reason:
                messages.error(request, "Please provide a reason for holding.")
            else:
                txn.status = "HOLD"
                txn.hold_reason = hold_reason
                txn.save()
                messages.success(request, f"{txn.employee.name} salary placed on hold.")

        elif action == "unhold":
            txn.status = "PENDING"
            txn.hold_reason = None
            txn.save()
            messages.success(request, f"Hold removed for {txn.employee.name}.")

        elif action == "mark_ready":
            if txn.status == "PENDING":
                txn.status = "READY"
                txn.save()
                messages.success(request, f"{txn.employee.name} marked as Ready for Export.")

        return redirect(request.path + f"?month={month}&year={year}&company={company_id or ''}&status={status_filter}")

    # -----------------------------------------------
    # LOAD TRANSACTIONS
    # -----------------------------------------------
    if company_id:
        selected_company = get_object_or_404(
            Company,
            id=company_id,
            organisation=organisation
        )

        batch = SalaryBatch.objects.filter(
            company=selected_company,
            month=month,
            year=year
        ).first()

        if batch:
            transactions = SalaryTransaction.objects.filter(
                batch=batch
            ).select_related("employee")

            if status_filter != "ALL":
                transactions = transactions.filter(status=status_filter)

    # -----------------------------------------------
    # SUMMARY COUNTS
    # -----------------------------------------------
    summary = {}
    if selected_company:
        batch = SalaryBatch.objects.filter(
            company=selected_company, month=month, year=year
        ).first()
        if batch:
            all_txns = SalaryTransaction.objects.filter(batch=batch)
            summary = {
                "PENDING": all_txns.filter(status="PENDING").count(),
                "HOLD":    all_txns.filter(status="HOLD").count(),
                "READY":   all_txns.filter(status="READY").count(),
                "EXPORTED": all_txns.filter(status="EXPORTED").count(),
                "COMPLETED": all_txns.filter(status="COMPLETED").count(),
            }

    context = {
        "companies": companies,
        "selected_company": selected_company,
        "transactions": transactions,
        "month": month,
        "year": year,
        "months": range(1, 13),
        "years": range(today.year - 3, today.year + 2),
        "status_filter": status_filter,
        "summary": summary,
    }

    return render(request, "reports/transaction_status_manager.html", context)

@login_required
def reprocess_bank_snapshot(request):
    if request.method != "POST":
        return redirect("reports:salary_report")

    company_id = request.POST.get("company")
    month = request.POST.get("month")
    year = request.POST.get("year")

    organisation = request.user.organisation_user.organisation

    company = get_object_or_404(Company, id=company_id, organisation=organisation)

    batch = get_object_or_404(SalaryBatch, company=company, month=month, year=year)

    transactions = SalaryTransaction.objects.filter(
        batch=batch
    ).select_related("employee")

    updated = 0
    skipped = 0

    for txn in transactions:
        # Fetch current active bank account for this employee
        active_bank = EmployeeBankAccount.objects.filter(
            employee=txn.employee,
            is_active=True
        ).first()

        if active_bank:
            txn.account_number = active_bank.account_number
            txn.ifsc = active_bank.ifsc
            txn.save(update_fields=["account_number", "ifsc"])
            updated += 1
        else:
            skipped += 1

    messages.success(
        request,
        f"Reprocessed {updated} transactions with bank data. "
        f"{skipped} skipped (no active bank account found)."
    )

    return redirect(
        f"{reverse('reports:salary_report')}?company={company_id}&month={month}&year={year}"
    )