from django.urls import path
from . import views

app_name = "banking"

urlpatterns = [
    path("bank-change-approvals/", views.approval_queue, name="bank_change_approval_list"),
    path("approve-bank-change/<int:id>/", views.approve_request, name="approve_bank_change"),
    path("response-upload/", views.upload_bank_response, name="bank_response_upload"),
    path("export/<int:month>/<int:year>/",views.export_bank_file, name="bank_export"),
    path("retry-failed/<int:batch_id>/", views.retry_failed_transactions, name="retry_failed"),

]
