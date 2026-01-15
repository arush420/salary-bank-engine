from django.urls import path
from . import views

urlpatterns = [
    path("bank-change/", views.request_bank_change, name="bank_change"),
]
