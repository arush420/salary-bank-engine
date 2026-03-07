from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views

urlpatterns = [

    path("admin/", admin.site.urls),

    # 🔐 AUTH
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="registration/login.html"
        ),
        name="login",
    ),

    path(
        "logout/",
        auth_views.LogoutView.as_view(),
        name="logout",
    ),

    # ⭐ ADD THIS LINE (IMPORTANT)
    path("accounts/", include("django.contrib.auth.urls")),

    # 🏠 ROOT → LOGIN
    path(
        "",
        auth_views.LoginView.as_view(
            template_name="registration/login.html"
        )
    ),

    # 🔒 PROTECTED APPS
    path("accounts/", include("accounts.urls")),
    path("dashboard/", include("dashboard.urls")),
    path("companies/", include("companies.urls")),
    path("employees/", include("employees.urls")),
    path("payroll/", include("payroll.urls")),
    path("banking/", include("banking.urls")),
    path("reports/", include("reports.urls")),
]