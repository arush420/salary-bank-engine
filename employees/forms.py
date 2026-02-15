from django import forms
from .models import EmployeeDraft

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