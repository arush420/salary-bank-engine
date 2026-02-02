from django.contrib.auth.models import User
from django.db import models


class Organisation(models.Model):
    name = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class OrganisationUser(models.Model):
    ROLE_CHOICES = (
        ("ADMIN", "Admin"),
        ("MANAGER", "Manager"),
        ("SUPERVISOR", "Supervisor"),
    )

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="organisation_user"
    )
    organisation = models.ForeignKey(
        Organisation,
        on_delete=models.CASCADE,
        related_name="users"
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    def __str__(self):
        return f"{self.user.username} → {self.organisation.name} ({self.role})"


class Company(models.Model):
    organisation = models.ForeignKey(
        Organisation,
        on_delete=models.CASCADE,
        related_name="companies",
        null = True,  # 👈 TEMPORARY
        blank = True  # 👈 TEMPORARY
    )
    name = models.CharField(max_length=200)

    serial_no = models.PositiveIntegerField()
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("organisation", "serial_no")
        ordering = ["serial_no"]
        indexes = [
            models.Index(fields=["organisation", "serial_no"]),
        ]

    def __str__(self):
        return f"{self.serial_no}. {self.name}"


class CompanyUser(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="company_access"
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="company_users"
    )

    class Meta:
        unique_together = ("user", "company")
        indexes = [
            models.Index(fields=["user", "company"]),
        ]

    def __str__(self):
        return f"{self.user.username} → {self.company}"
