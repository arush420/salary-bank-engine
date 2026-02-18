from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import models
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render

from companies.models import Company
from employees.models import (
    Employee,
    EmployeeDraft,
    EmployeeChangeRequest,
)
from banking.models import BankChangeRequest
from payroll.models import (
    SalaryBatch,
    SalaryBatchReversal,
    SalaryTransaction,
)

from .utils import can_reverse_batch


# -------------------------------------------------
# DASHBOARD HOME
# -------------------------------------------------
@login_required
def home(request):
    from datetime import date
    from django.db.models import Sum

    today = date.today()
    current_month = today.month
    current_year = today.year

    # =========================================
    # ORGANISATION LEVEL DATA
    # =========================================

    organisation = request.user.organisation_user.organisation

    companies = Company.objects.filter(organisation=organisation)
    employees = Employee.objects.filter(company__organisation=organisation)

    total_companies = companies.count()
    total_employees = employees.count()
    active_employees = employees.filter(exit_date__isnull=True).count()

    # =========================================
    # CURRENT MONTH PAYROLL SUMMARY
    # =========================================

    batches = SalaryBatch.objects.filter(
        company__organisation=organisation,
        month=current_month,
        year=current_year
    )

    transactions = SalaryTransaction.objects.filter(batch__in=batches)

    payroll_summary = {
        "total": transactions.aggregate(total=Sum("salary_amount"))["total"] or 0,
        "processed": transactions.filter(status="PROCESSED").aggregate(
            total=Sum("salary_amount")
        )["total"] or 0,
        "pending": transactions.filter(status="PENDING").count(),
        "hold": transactions.filter(status="HOLD").aggregate(
            total=Sum("salary_amount")
        )["total"] or 0,
        "failed": transactions.filter(status="FAILED").aggregate(
            total=Sum("salary_amount")
        )["total"] or 0,
    }

    context = {
        "total_companies": total_companies,
        "total_employees": total_employees,
        "active_employees": active_employees,
        "payroll_summary": payroll_summary,
        "month": current_month,
        "year": current_year,
    }

    if request.user.is_staff:
        context.update({
            "pending_employee_drafts": EmployeeDraft.objects.filter(status="PENDING").count(),
            "pending_profile_changes": EmployeeChangeRequest.objects.filter(status="PENDING").count(),
            "pending_bank_changes": BankChangeRequest.objects.filter(status="PENDING").count(),
        })

    return render(request, "dashboard/home.html", context)


# -------------------------------------------------
# SALARY DASHBOARD
# -------------------------------------------------
@login_required
def salary_dashboard(request):
    today = date.today()

    month = int(request.GET.get("month", today.month))
    year = int(request.GET.get("year", today.year))

    batch = SalaryBatch.objects.filter(
        month=month,
        year=year
    ).first()

    context = {
        "month": month,
        "year": year,
        "months": range(1, 13),
        "years": range(today.year - 2, today.year + 3),
        "batch": batch,
    }

    if not batch:
        return render(request, "dashboard/salary_dashboard.html", context)

    qs = SalaryTransaction.objects.filter(batch=batch)

    context["stats"] = {
        "pending": qs.filter(status="PENDING").count(),
        "hold": qs.filter(status="HOLD").count(),
        "processed": qs.filter(status="PROCESSED").count(),
        "failed": qs.filter(status="FAILED").count(),
        "total_amount": qs.aggregate(
            total=Sum("salary_amount")
        )["total"] or 0,
        "processed_amount": qs.filter(
            status="PROCESSED"
        ).aggregate(total=Sum("salary_amount"))["total"] or 0,
        "hold_amount": qs.filter(
            status="HOLD"
        ).aggregate(total=Sum("salary_amount"))["total"] or 0,
    }

    return render(request, "dashboard/salary_dashboard.html", context)


# -------------------------------------------------
# SALARY STATUS LIST
# -------------------------------------------------
@login_required
def salary_status_list(request, status):
    month = int(request.GET.get("month"))
    year = int(request.GET.get("year"))

    batch = SalaryBatch.objects.filter(
        month=month,
        year=year
    ).first()

    transactions = SalaryTransaction.objects.none()

    if batch:
        transactions = SalaryTransaction.objects.select_related(
            "employee"
        ).filter(
            batch=batch,
            status=status.upper()
        )

    context = {
        "status": status.upper(),
        "month": month,
        "year": year,
        "transactions": transactions,
    }

    return render(request, "dashboard/salary_status_list.html", context)


# -------------------------------------------------
# EMPLOYEE SALARY LEDGER
# -------------------------------------------------
@login_required
def employee_salary_ledger(request, employee_id):
    employee = get_object_or_404(Employee, id=employee_id)

    transactions = SalaryTransaction.objects.filter(
        employee=employee
    ).select_related(
        "batch"
    ).order_by(
        "-batch__year", "-batch__month"
    )

    totals = transactions.aggregate(
        total_amount=Sum("salary_amount"),
        processed_amount=Sum(
            "salary_amount",
            filter=models.Q(status="PROCESSED")
        ),
        pending_amount=Sum(
            "salary_amount",
            filter=models.Q(status="PENDING")
        ),
        hold_amount=Sum(
            "salary_amount",
            filter=models.Q(status="HOLD")
        ),
        failed_amount=Sum(
            "salary_amount",
            filter=models.Q(status="FAILED")
        ),
    )

    totals = {k: v or 0 for k, v in totals.items()}

    context = {
        "employee": employee,
        "transactions": transactions,
        "totals": totals,
    }

    return render(
        request,
        "dashboard/employee_salary_ledger.html",
        context
    )


# -------------------------------------------------
# SALARY BATCH REVERSAL
# -------------------------------------------------
@login_required
def reverse_batch_confirm(request, batch_id):
    batch = get_object_or_404(SalaryBatch, id=batch_id)

    if not can_reverse_batch(request.user):
        raise PermissionDenied("Not allowed")

    if batch.status == "COMPLETED":
        messages.error(request, "Completed batch cannot be reversed.")
        return redirect("dashboard:salary_dashboard")

    if request.method == "POST":
        reason = request.POST.get("reason")
        if not reason:
            messages.error(request, "Reason is required.")
            return redirect(request.path)

        batch.status = "REVERSED"
        batch.save(update_fields=["status"])

        SalaryBatchReversal.objects.create(
            batch=batch,
            reversed_by=request.user,
            reason=reason,
        )

        messages.success(request, "Salary batch reversed successfully.")
        return redirect("dashboard:salary_dashboard")

    return render(
        request,
        "dashboard/reverse_batch_confirm.html",
        {"batch": batch}
    )


# -------------------------------------------------
# APPROVALS DASHBOARD (ONE-STOP)
# -------------------------------------------------
@login_required
def approvals_dashboard(request):
    if not request.user.is_staff:
        raise PermissionDenied

    context = {
        "employee_drafts": EmployeeDraft.objects.filter(
            status="PENDING"
        )[:10],
        "employee_changes": EmployeeChangeRequest.objects.filter(
            status="PENDING"
        )[:10],
        "bank_changes": BankChangeRequest.objects.filter(
            status="PENDING"
        )[:10],
    }

    return render(request, "dashboard/approvals.html", context)
