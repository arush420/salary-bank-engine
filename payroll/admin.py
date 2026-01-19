from django.contrib import admin
from payroll.models import SalaryBatch, SalaryTransaction


@admin.register(SalaryBatch)
class SalaryBatchAdmin(admin.ModelAdmin):
    list_display = ("company", "month", "year", "status", "created_at")
    list_filter = ("status", "year")
    readonly_fields = ("created_at",)

    def has_change_permission(self, request, obj=None):
        # Batch can only be edited in DRAFT
        if obj and obj.status != "DRAFT":
            return False
        return super().has_change_permission(request, obj)


@admin.register(SalaryTransaction)
class SalaryTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "employee",
        "batch",
        "salary_amount",
        "status",
        "utr",
    )

    list_filter = ("status", "batch__year", "batch__month")
    search_fields = ("employee__emp_code", "employee__name", "utr")

    readonly_fields = (
        "batch",
        "employee",
        "salary_amount",
        "account_number",
        "ifsc",
        "hold_reason",
        "created_at",
    )

    def has_change_permission(self, request, obj=None):
        """
        Allow editing ONLY for bank response fields
        after batch is exported.
        """
        if obj and obj.batch.status != "DRAFT":
            return True  # allow bank response updates
        return super().has_change_permission(request, obj)

    def get_readonly_fields(self, request, obj=None):
        """
        Lock salary fields permanently,
        allow only bank response fields after export.
        """
        if obj and obj.batch.status != "DRAFT":
            return self.readonly_fields + (
                "status",
                "salary_amount",
            )
        return self.readonly_fields
