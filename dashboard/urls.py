from django.urls import path
from .views import salary_dashboard, salary_status_list

app_name = "dashboard"

urlpatterns = [
    path("", salary_dashboard, name="salary_dashboard"),
    path("list/<str:status>/", salary_status_list, name="salary_status_list"),
]
