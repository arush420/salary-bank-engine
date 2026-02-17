from django.urls import path
from . import views

app_name = "payroll"

urlpatterns = [
    path("upload/", views.upload_salary, name="salary_upload"),
    path(
        "template/<int:company_id>/",
        views.download_salary_template,
        name="salary_template"
    ),

    path("batch/<int:batch_id>/", views.salary_batch_detail, name="batch_detail"),
    path("batch/<int:batch_id>/finalize/", views.finalize_batch, name="finalize_batch"),
    path("batch/<int:batch_id>/export/", views.export_batch, name="export_batch"),
    path("batches/", views.salary_batch_list, name="batch_list"),


]

