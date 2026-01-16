from django.urls import path
from .views import salary_dashboard

app_name = "dashboard"

urlpatterns = [
    path("", salary_dashboard, name="salary_dashboard"),
]
