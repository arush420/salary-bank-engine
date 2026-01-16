from django.urls import path
from . import views

app_name = "payroll"

urlpatterns = [
    path("upload/", views.upload_salary, name="salary_upload"),
]
