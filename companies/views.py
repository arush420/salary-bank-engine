from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render, get_object_or_404
from django.db import transaction
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from django.views.decorators.http import require_POST

from banking.models import BankChangeRequest
from companies.forms import CompanyForm
from companies.models import Organisation, OrganisationUser, Company
from companies.utils import get_user_organisation
from django.conf import settings

from employees.models import EmployeeDraft, Employee, EmployeeChangeRequest
from payroll.models import SalaryBatch, SalaryTransaction

if not settings.DEBUG:
    raise PermissionDenied("Hard delete disabled in production")


def register(request):
    if request.method == "POST":
        user_form = UserCreationForm(request.POST)
        organisation_name = request.POST.get("organisation_name")

        if not organisation_name:
            messages.error(request, "Organisation name is required.")
            return render(request, "registration/register.html", {"form": user_form})

        if user_form.is_valid():
            with transaction.atomic():
                # 1️⃣ Create user
                user = user_form.save()

                # 2️⃣ Create organisation
                organisation = Organisation.objects.create(
                    name=organisation_name.strip()
                )

                # 3️⃣ Make user ADMIN of organisation
                OrganisationUser.objects.create(
                    user=user,
                    organisation=organisation,
                    role="ADMIN"
                )

            # 4️⃣ Login user
            login(request, user)

            # 5️⃣ Redirect to dashboard
            return redirect("dashboard:home")

    else:
        user_form = UserCreationForm()

    return render(
        request,
        "registration/register.html",
        {"form": user_form}
    )


@login_required
def company_create(request):
    """
    Register a new company under the logged-in user's organisation
    """
    org_user = OrganisationUser.objects.get(user=request.user)

    if request.method == "POST":
        form = CompanyForm(request.POST)
        if form.is_valid():
            Company.create_for_organisation(
                organisation=org_user.organisation,
                **form.cleaned_data
            )
            messages.success(request, "Company registered successfully.")
            return redirect("companies:company_list")
    else:
        form = CompanyForm()

    return render(
        request,
        "companies/company_form.html",
        {"form": form}
    )


@login_required
def company_list(request):
    """
    List all companies under the logged-in user's organisation
    """

    org_user = OrganisationUser.objects.filter(user=request.user).first()

    if not org_user:
        # Safety: user exists but not linked to organisation
        return render(
            request,
            "companies/company_list.html",
            {"companies": []}
        )

    companies = Company.objects.filter(
        organisation=org_user.organisation
    ).order_by("serial_no")

    return render(
        request,
        "companies/company_list.html",
        {"companies": companies}
    )


@login_required
def company_detail(request, pk):
    org_user = OrganisationUser.objects.filter(user=request.user).first()

    company = get_object_or_404(
        Company,
        pk=pk,
        organisation=org_user.organisation
    )

    return render(
        request,
        "companies/company_detail.html",
        {"company": company}
    )

@login_required
def company_edit(request, pk):
    organisation = get_user_organisation(request.user)

    company = get_object_or_404(
        Company,
        pk=pk,
        organisation=organisation
    )

    if request.method == "POST":
        form = CompanyForm(request.POST, instance=company)
        if form.is_valid():
            form.save()
            messages.success(request, "Company updated successfully.")
            return redirect("companies:company_list")
    else:
        form = CompanyForm(instance=company)

    return render(
        request,
        "companies/company_edit.html",
        {
            "company": company,
            "form": form,
        }
    )


@login_required
@require_POST
def company_delete(request, pk):
    organisation = get_user_organisation(request.user)

    company = get_object_or_404(
        Company,
        pk=pk,
        organisation=organisation
    )

    # ----------------------------
    # HARD DELETE (TEST MODE)
    # ----------------------------

    # 1️⃣ Employee Drafts
    EmployeeDraft.objects.filter(company=company).delete()

    # 2️⃣ Employees + related data
    employees = Employee.objects.filter(company=company)

    # Profile change requests
    EmployeeChangeRequest.objects.filter(employee__in=employees).delete()

    # Bank change requests
    BankChangeRequest.objects.filter(employee__in=employees).delete()

    # Salary data
    SalaryTransaction.objects.filter(employee__in=employees).delete()
    SalaryBatch.objects.filter(company=company).delete()

    # Employees
    employees.delete()

    # 3️⃣ Finally delete company
    company.delete()

    messages.success(
        request,
        f"Company '{company.name}' and ALL related data deleted (TEST MODE)."
    )

    return redirect("companies:company_list")


@login_required
def select_company(request, company_id):
    company = get_object_or_404(
        Company,
        id=company_id,
        organisation=request.organisation,
        is_active=True
    )

    # 🔑 store active company in session
    request.session["active_company_id"] = company.id

    return redirect("dashboard:home")