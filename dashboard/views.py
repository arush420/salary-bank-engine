from datetime import date
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import models
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render

from employees.models import Employee
from payroll.models import (
    SalaryBatch,
    SalaryBatchReversal,
    SalaryTransaction
)
from .utils import can_reverse_batch

@login_required
def home(request):
    return render(request, "dashboard/home.html")


def salary_dashboard(request):
    today = date.today()

    month = int(request.GET.get("month", today.month))
    year = int(request.GET.get("year", today.year))

    batch = SalaryBatch.objects.filter(
        month=month,
        year=year
    ).first()

    # Base context (always available)
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

    # Stats
    context["stats"] = {"pending": qs.filter(status="PENDING").count(),
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


def salary_status_list(request, status):
    month = int(request.GET.get("month"))
    year = int(request.GET.get("year"))

    batch = SalaryBatch.objects.filter(
        month=month,
        year=year
    ).first()

    transactions = []

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



def employee_salary_ledger(request, employee_id):
    employee = Employee.objects.get(id=employee_id)

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

    # Replace None with 0
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