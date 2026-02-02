from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import redirect, render
from django.db import transaction
from django.contrib import messages

from companies.models import Organisation, OrganisationUser


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
