from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from companies.models import Company


@login_required
def operations_home(request):
    """
    Operations landing page.
    Allows company selection and operation routing.
    """

    # ✅ SAFE access
    company = getattr(request, "company", None)
    companies = getattr(request, "available_companies", [])

    return render(
        request,
        "operations/operations_home.html",
        {
            "company": company,
            "companies": companies,
        }
    )




@login_required
def operations_launch(request):
    company_id = request.GET.get("company")
    op = request.GET.get("op")

    if company_id:
        request.session["active_company_id"] = int(company_id)

    if not op:
        return redirect("operations:home")

    if op == "employees":
        return redirect("employees:employee_list")

    if op == "payroll":
        return redirect("payroll:salary_upload")

    if op == "bank":
        return redirect("banking:bank_response_upload")

    if op == "reports":
        return redirect("dashboard:home")

    return redirect("operations:home")
