from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import redirect, render, get_object_or_404
from django.db import transaction
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages

from companies.models import Organisation, OrganisationUser, Company


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
def create_company(request):
    org_user = OrganisationUser.objects.filter(user=request.user).first()

    if not org_user:
        messages.error(request, "Organisation not found for this user.")
        return redirect("dashboard:home")

    if request.method == "POST":
        name = request.POST.get("name")

        if not name:
            messages.error(request, "Company name is required.")
            return redirect("companies:create_company")

        # Auto-generate serial_no per organisation
        next_serial = (
            Company.objects.filter(organisation=org_user.organisation)
            .count() + 1
        )

        company = Company.objects.create(
            organisation=org_user.organisation,
            name=name,
            serial_no=next_serial,
        )

        # Set this company as active
        request.session["active_company_id"] = company.id

        messages.success(request, f"Company '{company.name}' created successfully.")
        return redirect("dashboard:home")

    return render(request, "companies/create_company.html")

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