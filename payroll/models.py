from django.contrib.auth.models import User
from django.db import models
from companies.models import Company
from employees.models import Employee


# =========================
# Salary Batch
# =========================

class SalaryBatch(models.Model):
    STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("EXPORTED", "Exported to Bank"),
        ("COMPLETED", "Completed"),
        ("REVERSED", "Reversed"),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    month = models.PositiveIntegerField()
    year = models.PositiveIntegerField()

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="DRAFT"
    )

    reversal_reason = models.TextField(
        null=True,
        blank=True,
        help_text="Reason for reversing this batch (admin only)"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("company", "month", "year")
        ordering = ["-year", "-month"]

    def __str__(self):
        return f"{self.company} - {self.month}/{self.year}"



# =========================
# Salary Transaction
# =========================

class SalaryTransaction(models.Model):
    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("HOLD", "Hold"),
        ("PROCESSED", "Processed"),
        ("FAILED", "Failed"),
        ("CANCELLED", "Cancelled"),
    ]

    batch = models.ForeignKey(
        SalaryBatch,
        on_delete=models.CASCADE,
        related_name="transactions"
    )

    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="salary_transactions"
    )

    salary_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    # Bank snapshot at the time of payroll
    account_number = models.CharField(
        max_length=30,
        null=True,
        blank=True
    )

    ifsc = models.CharField(
        max_length=15,
        null=True,
        blank=True
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING"
    )

    # Why salary was put on HOLD
    hold_reason = models.CharField(
        max_length=255,
        null=True,
        blank=True
    )

    # Why bank processing failed
    failure_reason = models.CharField(
        max_length=255,
        null=True,
        blank=True
    )

    # Bank processing info
    utr = models.CharField(
        max_length=100,
        null=True,
        blank=True
    )

    bank_response_at = models.DateTimeField(
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("batch", "employee")
        indexes = [
            models.Index(fields=["employee"]),
            models.Index(fields=["batch"]),
            models.Index(fields=["status"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.employee.emp_code} | {self.batch.month}/{self.batch.year} | {self.status}"

# =========================
# Salary Batch reversal by admin
# =========================
class SalaryBatchReversal(models.Model):
    batch = models.OneToOneField(
        SalaryBatch,
        on_delete=models.CASCADE,
        related_name="reversal"
    )
    reason = models.TextField()
    reversed_by = models.ForeignKey(User, on_delete=models.PROTECT)
    reversed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Reversal: {self.batch}"
