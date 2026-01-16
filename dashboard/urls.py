from django.urls import path
from .views import salary_dashboard

urlpatterns = [
    path("", salary_dashboard, name="salary_dashboard"),
]
