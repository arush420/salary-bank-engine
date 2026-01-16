from django.shortcuts import render
from payroll.models import SalaryBatch, SalaryTransaction
from companies.models import Company
from django.db.models import Count, Sum


def salary_dashboard(request):
    # Temporary defaults (can add dropdown later)
    month = int(request.GET.get("month", 1))
    year = int(request.GET.get("year", 2026))

    company = Company.objects.first()

    batch = SalaryBatch.objects.filter(
        company=company,
        month=month,
        year=year
    ).first()

    context = {
        "month": month,
        "year": year,
        "stats": {},
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
