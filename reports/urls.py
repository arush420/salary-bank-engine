from django.urls import path
from . import views

app_name = "reports"

urlpatterns = [
    path("", views.reports_dashboard, name="dashboard"),
    path("salary/", views.salary_report, name="salary_report"),
    path("bank-changes/", views.bank_change_report, name="bank_change_report"),
    path("salary/yearly/", views.yearly_salary_report, name="yearly_salary_report"),
    path("salary/transaction-status/", views.transaction_status_manager, name="transaction_status_manager"),
    path("salary/reprocess-bank/", views.reprocess_bank_snapshot, name="reprocess_bank_snapshot"),
]
