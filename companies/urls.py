from django.urls import path
from . import views

app_name = "companies"

urlpatterns = [
    path("create/", views.create_company, name="create_company"),
    path("register/", views.register, name="register"),
]
