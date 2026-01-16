from django.urls import path
from . import views

app_name = "banking"

urlpatterns = [
    path("approvals/", views.approval_queue, name="approval_queue"),
    path("approve/<int:id>/", views.approve_request, name="approve_request"),
    path("response-upload/", views.upload_bank_response, name="bank_response_upload"),
    path("export/<int:month>/<int:year>/",views.export_bank_file, name="bank_export"),

]
