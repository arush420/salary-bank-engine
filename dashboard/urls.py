from django.urls import path
from .views import salary_dashboard, salary_status_list, employee_salary_ledger

app_name = "dashboard"

urlpatterns = [
    path("", salary_dashboard, name="salary_dashboard"),
    path("list/<str:status>/", salary_status_list, name="salary_status_list"),
    path("employee/<int:employee_id>/", employee_salary_ledger, name="employee_salary_ledger"),
]
