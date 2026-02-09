from django.urls import path
from .views import salary_dashboard, salary_status_list, employee_salary_ledger
from . import views
app_name = "dashboard"

urlpatterns = [
    path("",  views.home, name="home"),
    path("list/<str:status>/", salary_status_list, name="salary_status_list"),
    path("employee/<int:employee_id>/", employee_salary_ledger, name="employee_salary_ledger"),
    path("reverse/<int:batch_id>/", views.reverse_batch_confirm, name="reverse_batch_confirm"),
    path("approvals/", views.approvals_dashboard, name="approvals")

]
