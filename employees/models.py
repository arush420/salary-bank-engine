from django.db import models
from django.contrib.auth.models import User
from companies.models import Company

class Employee(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    emp_code = models.CharField(max_length=50)
    name = models.CharField(max_length=200)
    default_salary = models.DecimalField(max_digits=10, decimal_places=2)
    joining_date = models.DateField()
    exit_date = models.DateField(null=True, blank=True)

    class Meta:
        unique_together = ('company', 'emp_code')

    def __str__(self):
        return f"{self.emp_code} - {self.name}"




