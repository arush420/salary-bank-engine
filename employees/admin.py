from django.contrib import admin
from .models import Employee, EmployeeBankAccount, BankChangeRequest

admin.site.register(Employee)
admin.site.register(EmployeeBankAccount)
admin.site.register(BankChangeRequest)
