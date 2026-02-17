from django import forms
from datetime import datetime


class SalaryUploadForm(forms.Form):

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

    month = forms.ChoiceField(
        choices=MONTH_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"})
    )

    year = forms.ChoiceField(
        choices=[],
        widget=forms.Select(attrs={"class": "form-select"})
    )

    file = forms.FileField(
        widget=forms.FileInput(attrs={"class": "form-control"})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        current_year = datetime.now().year

        self.fields["year"].choices = [
            (current_year - 1, current_year - 1),
            (current_year, current_year),
            (current_year + 1, current_year + 1),
        ]

        self.fields["year"].initial = current_year
