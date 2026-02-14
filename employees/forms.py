from django import forms
from .models import EmployeeDraft
from banking.models import BankChangeRequest


class BankChangeRequestForm(forms.ModelForm):
    MONTH_CHOICES = [
        (1, "January"),
        (2, "February"),
        (3, "March"),
        (4, "April"),
        (5, "May"),
        (6, "June"),
        (7, "July"),
        (8, "August"),
        (9, "September"),
        (10, "October"),
        (11, "November"),
        (12, "December"),
    ]

    effective_month = forms.ChoiceField(
        choices=MONTH_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"})
    )

    class Meta:
        model = BankChangeRequest
        fields = [
            "new_bank_name",
            "new_account_number",
            "new_ifsc",
            "effective_month",
            "effective_year",
        ]
        widgets = {
            "new_bank_name": forms.TextInput(attrs={"class": "form-control"}),
            "new_account_number": forms.TextInput(attrs={"class": "form-control"}),
            "new_ifsc": forms.TextInput(attrs={"class": "form-control"}),
            "effective_year": forms.NumberInput(attrs={"class": "form-control"}),
        }


class EmployeeDraftForm(forms.ModelForm):
    class Meta:
        model = EmployeeDraft
        fields = [
            "emp_code",
            "name",
            "father_name",
            "uan_number",
            "esic_number",
            "document_number",
            "joining_date",
            "default_salary",
        ]

        widgets = {
            "joining_date": forms.DateInput(attrs={"type": "date"}),
        }