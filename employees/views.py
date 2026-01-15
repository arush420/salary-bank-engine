from django.shortcuts import render, redirect
# from django.contrib.auth.decorators import login_required
from .forms import BankChangeRequestForm
from .models import Employee

# @login_required
def request_bank_change(request):
    employee = Employee.objects.first()

    if request.method == "POST":
        form = BankChangeRequestForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.employee = employee
            obj.submitted_by = request.user
            obj.save()
            return redirect("bank_request_success")
    else:
        form = BankChangeRequestForm()

    return render(request, "employees/bank_request.html", {"form": form})
