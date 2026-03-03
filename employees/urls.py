from django.urls import path
from . import views

app_name = "employees"

urlpatterns = [

    # =========================
    # EMPLOYEE MASTER
    # =========================
    path("", views.employee_list, name="employee_list"),
    path("<int:employee_id>/", views.employee_profile, name="employee_profile"),
    path("<int:employee_id>/delete/", views.delete_employee, name="employee_delete"),

    # =========================
    # PROFILE CHANGE REQUESTS
    # =========================
    path("<int:employee_id>/change/", views.request_employee_change, name="employee_change_request"),
    path("<int:employee_id>/change/approve/", views.approve_employee_change, name="approve_employee_change"),
    path("<int:employee_id>/change/reject/", views.reject_employee_change, name="reject_employee_change"),
    path("changes/approval/", views.employee_change_approval_list, name="employee_change_approval_list"),

    # =========================
    # BANK CHANGE REQUEST
    # =========================
    path("<int:employee_id>/bank-change/", views.request_bank_change, name="bank_change"),

    # =========================
    # DRAFTS (ONBOARDING)
    # =========================
    path("drafts/", views.employee_draft_list, name="employee_draft_list"),
    path("drafts/new/", views.employee_draft_create, name="employee_draft_create"),
    path("drafts/template/", views.download_employee_draft_template, name="employee_draft_template"),
    path("drafts/upload/", views.upload_employee_drafts, name="upload_employee_drafts"),
    path("drafts/upload/errors/", views.download_employee_draft_errors, name="employee_draft_upload_errors"),
    path("drafts/approval/", views.employee_draft_approval_list, name="employee_draft_approval_list"),
    path("drafts/<int:draft_id>/approve/", views.approve_employee_draft, name="approve_employee_draft"),
    path("drafts/<int:draft_id>/reject/", views.reject_employee_draft, name="reject_employee_draft"),
    path("drafts/<int:draft_id>/merge/", views.merge_employee_draft, name="merge_employee_draft"),

]