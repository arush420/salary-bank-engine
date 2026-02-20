from django.db import models
from django.contrib.auth.models import User
from django.db.models import Q

from employees.models import Employee


class EmployeeBankAccount(models.Model):

    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="bank_accounts"
    )

    bank_name = models.CharField(max_length=200)
    account_number = models.CharField(max_length=30)
    ifsc = models.CharField(max_length=11)

    effective_from_month = models.DateField()

    is_active = models.BooleanField(default=True)

    approved_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )

    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-effective_from_month"]

        constraints = [
            models.UniqueConstraint(
                fields=["employee", "account_number"],
                condition=Q(is_active=True),
                name="unique_active_bank_account_per_employee"
            )
        ]

        indexes = [
            models.Index(fields=["employee", "is_active"]),
        ]

    def __str__(self):
        return f"{self.employee.emp_code} - {self.account_number}"


class BankChangeRequest(models.Model):

    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]

    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="bank_change_requests"
    )

    new_bank_name = models.CharField(max_length=200)
    new_account_number = models.CharField(max_length=30)
    new_ifsc = models.CharField(max_length=15)

    # Payroll-ready structure
    effective_month = models.PositiveSmallIntegerField(null=True, blank=True)
    effective_year = models.PositiveSmallIntegerField(null=True, blank=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING"
    )

    submitted_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="bank_requests"
    )

    approved_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_bank_requests"
    )

    submitted_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    rejection_reason = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ["-submitted_at"]


    def __str__(self):
        return f"{self.employee.emp_code} → {self.new_bank_name} ({self.status})"
