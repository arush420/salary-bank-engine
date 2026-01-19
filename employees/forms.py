from django import forms
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