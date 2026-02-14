from django import forms
from datetime import datetime
from .models import BankChangeRequest


class BankResponseUploadForm(forms.Form):
    month = forms.IntegerField()
    year = forms.IntegerField()
    file = forms.FileField()


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
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Effective From Month"
    )

    effective_year = forms.ChoiceField(
        choices=[],
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Effective Year"
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
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        current_year = datetime.now().year

        self.fields["effective_year"].choices = [
            (current_year - 1, current_year - 1),
            (current_year, current_year),
            (current_year + 1, current_year + 1),
        ]

        self.fields["effective_year"].initial = current_year
