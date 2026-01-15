from django import forms

class SalaryUploadForm(forms.Form):
    month = forms.IntegerField()
    year = forms.IntegerField()
    file = forms.FileField()
