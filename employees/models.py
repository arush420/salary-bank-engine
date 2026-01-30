from django.db import models
from django.contrib.auth.models import User
from companies.models import Company


# =========================
# APPROVED EMPLOYEE MASTER
# =========================
# This model stores ONLY approved, authoritative employee data.
# All edits must go through EmployeeChangeRequest (no direct edits).
class Employee(models.Model):
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="employees"
    )

    emp_code = models.CharField(max_length=50)
    name = models.CharField(max_length=200)
    father_name = models.CharField(max_length=200, blank=True)

    # Statutory identifiers (optional but unique if present)
    uan_number = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True
    )
    esic_number = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True
    )
    document_number = models.CharField(
        max_length=50,
        unique=True,
        null=True,
        blank=True
    )

    # Default salary reference (actual salary generated elsewhere)
    default_salary = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )

    joining_date = models.DateField()
    exit_date = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    # Admin who approved this employee
    approved_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_employees"
    )

    class Meta:
        unique_together = ("company", "emp_code")
        ordering = ["emp_code"]

    def __str__(self):
        return f"{self.emp_code} - {self.name}"


# =========================
# EMPLOYEE DRAFT (ONBOARDING)
# =========================
# Temporary holding model for onboarding via form or Excel upload.
# Data moves to Employee ONLY after admin approval.
class EmployeeDraft(models.Model):
    STATUS_CHOICES = [
        ("PENDING", "Pending Approval"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
    ]

    company = models.ForeignKey(Company, on_delete=models.PROTECT)

    emp_code = models.CharField(max_length=50)
    name = models.CharField(max_length=200)
    father_name = models.CharField(max_length=200, blank=True)

    uan_number = models.CharField(max_length=20, null=True, blank=True)
    esic_number = models.CharField(max_length=20, null=True, blank=True)
    document_number = models.CharField(max_length=50, null=True, blank=True)

    joining_date = models.DateField()

    default_salary = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="employee_drafts"
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("company", "emp_code")


# =========================
# AUDIT LOG (IMMUTABLE)
# =========================
# Central system-wide audit trail.
# Never edited or deleted.
class AuditLog(models.Model):
    action = models.CharField(max_length=100)
    description = models.TextField()

    performed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.action} @ {self.created_at}"


# =========================
# EMPLOYEE CHANGE REQUEST
# =========================
# Handles ALL employee profile edits via JSON-based diff.
# Approved requests auto-apply to Employee.
class EmployeeChangeRequest(models.Model):
    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
    ]

    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="change_requests"
    )

    # JSON structure example:
    # {
    #   "name": {"old": "Rahul", "new": "Rahul Kumar"},
    #   "father_name": {"old": "Suresh", "new": "Suresh Lal"}
    # }
    changes = models.JSONField()

    requested_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="employee_change_requests"
    )

    requested_at = models.DateTimeField(auto_now_add=True)

    reviewed_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_employee_changes"
    )

    reviewed_at = models.DateTimeField(null=True, blank=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING"
    )

    rejection_reason = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.employee.emp_code} - {self.status}"