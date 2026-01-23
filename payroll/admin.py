from django.contrib import admin, messages
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils import timezone
from django.urls import path
from payroll.models import (SalaryBatch, SalaryTransaction, SalaryBatchReversal)


@admin.register(SalaryBatch)
class SalaryBatchAdmin(admin.ModelAdmin):
    list_display = ("company", "month", "year", "status", "created_at")
    list_filter = ("status", "year")
    actions = ["reverse_batch"]

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "reverse-confirm/",
                self.admin_site.admin_view(self.reverse_confirm),
                name="salarybatch_reverse_confirm",
            ),
        ]
        return custom_urls + urls

    def reverse_batch(self, request, queryset):
        ids = queryset.values_list("id", flat=True)
        return redirect(
            f"reverse-confirm/?ids={','.join(map(str, ids))}"
        )

    reverse_batch.short_description = "⚠️ Reverse selected batches"

    def reverse_confirm(self, request):
        ids = request.GET.get("ids", "")
        batches = SalaryBatch.objects.filter(id__in=ids.split(","))

        if request.method == "POST":
            reason = request.POST.get("reason", "Admin reversal")

            for batch in batches:
                if batch.status == "COMPLETED":
                    self.message_user(
                        request,
                        f"Batch {batch} already completed. Skipped.",
                        level=messages.ERROR,
                    )
                    continue

                batch.status = "REVERSED"
                batch.save(update_fields=["status"])

                SalaryBatchReversal.objects.create(
                    batch=batch,
                    reversed_by=request.user,
                    reason=reason,
                )

            self.message_user(request, "Selected batches reversed successfully.")
            return redirect("..")

        return render(
            request,
            "admin/payroll/reverse_confirm.html",
            {"batches": batches},
        )

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
