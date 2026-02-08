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


from django.db.models import Max
from django.db import transaction

from django.db import models, transaction
from django.db.models import Max

class Company(models.Model):
    organisation = models.ForeignKey(
        Organisation,
        on_delete=models.CASCADE,
        related_name="companies"
    )

    # Core
    serial_no = models.PositiveIntegerField()
    name = models.CharField(max_length=200)

    # Address & GST
    address = models.TextField(blank=True)
    gst_number = models.CharField(max_length=15, blank=True, help_text="15-character GSTIN")

    # Contact Person
    contact_name = models.CharField(max_length=150, blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    contact_email = models.EmailField(blank=True)

    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("organisation", "serial_no")
        ordering = ["serial_no"]

    def __str__(self):
        return f"{self.serial_no}. {self.name}"

    @staticmethod
    def create_for_organisation(organisation, **data):
        """
        Safely create company with auto-increment serial_no per organisation
        """
        with transaction.atomic():
            last_serial = (Company.objects.filter(organisation=organisation).aggregate(Max("serial_no"))["serial_no__max"])
            next_serial = (last_serial or 0) + 1

            return Company.objects.create(organisation=organisation, serial_no=next_serial, **data)


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
