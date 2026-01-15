from django.urls import path
from . import views

urlpatterns = [
    path("upload/", views.upload_salary, name="salary_upload"),
]
