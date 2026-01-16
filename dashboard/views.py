from datetime import date
from django.shortcuts import render
from django.db.models import Sum
from payroll.models import SalaryBatch, SalaryTransaction


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
