from django.urls import path
from . import views
from .views import employee_list, employee_profile

app_name = "employees"

urlpatterns = [
    path("bank-change/", views.request_bank_change, name="bank_change"),
    path("", employee_list, name="employee_list"),
    path("<int:employee_id>/", employee_profile, name="employee_profile"),
]
