from django.db import models
from companies.models import Company
from employees.models import Employee

class SalaryBatch(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    month = models.IntegerField()
    year = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, default="DRAFT")

    class Meta:
        unique_together = ("company", "month", "year")

    def __str__(self):
        return f"{self.company} - {self.month}/{self.year}"


class SalaryTransaction(models.Model):
    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("HOLD", "Hold"),
        ("PROCESSED", "Processed"),
        ("FAILED", "Failed"),
        ("CANCELLED", "Cancelled"),
    ]

    batch = models.ForeignKey(SalaryBatch, on_delete=models.CASCADE)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)

    salary_amount = models.DecimalField(max_digits=10, decimal_places=2)

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

    hold_reason = models.CharField(
        max_length=255,
        null=True,
        blank=True
    )

    utr = models.CharField(max_length=100, null=True, blank=True)
    bank_response_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["employee"]),
            models.Index(fields=["batch"]),
            models.Index(fields=["status"]),
        ]
