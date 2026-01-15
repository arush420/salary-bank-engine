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
    account_number = models.CharField(max_length=30)
    ifsc = models.CharField(max_length=15)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    utr = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        unique_together = ("batch", "employee")
