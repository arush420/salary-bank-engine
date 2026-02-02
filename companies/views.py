from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import redirect, render
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
    # 🔒 Only Organisation Admin can create companies
    if request.role != "ADMIN":
        messages.error(request, "You are not allowed to create companies.")
        return redirect("dashboard:home")

    if request.method == "POST":
        name = request.POST.get("name")

        if not name:
            messages.error(request, "Company name is required.")
            return redirect("companies:create_company")

        Company.create_for_organisation(
            organisation=request.organisation,
            name=name
        )

        messages.success(request, "Company created successfully.")
        return redirect("dashboard:home")

    return render(request, "companies/create_company.html")
