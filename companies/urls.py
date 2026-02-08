from django.urls import path
from . import views

app_name = "companies"

urlpatterns = [
    # Company master
    path("", views.company_list, name="company_list"),
    path("create/", views.company_create, name="company_create"),
    # 🔍 View details
    path("<int:pk>/", views.company_detail, name="company_detail"),
    # ✏️ Edit
    path("<int:pk>/edit/", views.company_edit, name="company_edit"),
    # 🗑 Delete
    path("<int:pk>/delete/", views.company_delete, name="company_delete"),
    # Active company selection
    path("select/<int:company_id>/", views.select_company, name="select_company"),
    # Company activation (optional)
    path("<int:company_id>/select/", views.select_company, name="select_company"),

    # Organisation/ Account registration
    path("register/", views.register, name="register"),

]
