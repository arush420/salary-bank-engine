from django import forms
from .models import EmployeeDraft
from banking.models import BankChangeRequest


class BankChangeRequestForm(forms.ModelForm):
    class Meta:
        model = BankChangeRequest
        fields = [
            "new_bank_name",
            "new_account_number",
            "new_ifsc",
            "effective_from_month",
        ]
        widgets = {
            "effective_from_month": forms.NumberInput(
                attrs={"placeholder": "MM (e.g. 2 for Feb)"}
            )
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