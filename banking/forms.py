from django import forms

class BankResponseUploadForm(forms.Form):
    month = forms.IntegerField()
    year = forms.IntegerField()
    file = forms.FileField()
