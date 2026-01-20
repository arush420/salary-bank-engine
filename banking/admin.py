from django.contrib import admin
from .models import EmployeeBankAccount, BankChangeRequest


@admin.register(EmployeeBankAccount)
class EmployeeBankAccountAdmin(admin.ModelAdmin):
    list_display = (
        "employee",
        "bank_name",
        "account_number",
        "ifsc",
        "is_active",
        "approved_by",
        "approved_at",
    )
    list_filter = ("is_active", "bank_name")
    search_fields = ("employee__emp_code", "account_number")


@admin.register(BankChangeRequest)
class BankChangeRequestAdmin(admin.ModelAdmin):
    list_display = (
        "employee",
        "new_bank_name",
        "new_account_number",
        "status",
        "approved_at",
        "approved_by",
    )
    list_filter = ("status",)

