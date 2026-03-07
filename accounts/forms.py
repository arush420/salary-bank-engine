from django import forms
from django.contrib.auth.models import User


class ProfileForm(forms.ModelForm):

    full_name = forms.CharField(required=False)
    phone = forms.CharField(required=False)

    class Meta:
        model = User
        fields = ["email"]