from django.contrib import admin
from django.db import transaction
from django.utils import timezone

from payroll.models import (
    SalaryBatch,
    SalaryTransaction,
    SalaryBatchReversal,
)


@admin.register(SalaryBatch)
class SalaryBatchAdmin(admin.ModelAdmin):
    list_display = ("company", "month", "year", "status", "created_at")
    list_filter = ("status", "year")
    readonly_fields = ("created_at",)
    actions = ["reverse_batch"]

    def has_change_permission(self, request, obj=None):
        # Batch editable only in DRAFT
        if obj and obj.status != "DRAFT":
            return False
        return super().has_change_permission(request, obj)

    def reverse_batch(self, request, queryset):
        for batch in queryset:
            if batch.status == "REVERSED":
                self.message_user(request,f"{batch} is already reversed.",
                    level="warning",)
                continue

            with transaction.atomic():
                batch.status = "REVERSED"
                batch.save(update_fields=["status"])

                SalaryTransaction.objects.filter(
                    batch=batch
                ).exclude(
                    status__in=["PROCESSED", "CANCELLED"]
                ).update(
                    status="CANCELLED",
                    bank_response_at=timezone.now(),
                )

                SalaryBatchReversal.objects.create(
                    batch=batch,
                    reversed_by=request.user,
                    reason="Admin reversal via panel",
                )

        self.message_user(
            request,
            "Selected batches reversed safely.",
        )

    reverse_batch.short_description = "⚠️ Reverse selected batches (AUDITED)"

@admin.register(SalaryBatchReversal)
class SalaryBatchReversalAdmin(admin.ModelAdmin):
    list_display = ("batch", "reversed_by", "reversed_at", "reason")
    readonly_fields = ("batch", "reversed_by", "reversed_at", "reason")


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

    def get_readonly_fields(self, request, obj=None):
        """
        Salary fields are ALWAYS locked.
        Bank response fields remain editable.
        """
        if obj and obj.batch.status != "DRAFT":
            return self.readonly_fields + (
                "salary_amount",
                "account_number",
                "ifsc",
                "hold_reason",
            )
        return self.readonly_fields
