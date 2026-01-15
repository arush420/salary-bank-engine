from django import forms
from .models import BankChangeRequest

class BankChangeRequestForm(forms.ModelForm):
    class Meta:
        model = BankChangeRequest
        fields = ["new_bank_name", "new_account_number", "new_ifsc", "effective_from_month"]
        widgets = {
            "effective_from_month": forms.DateInput(attrs={"type": "month"})
        }
