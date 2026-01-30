from employees.models import Employee, AuditLog


def approve_employee(draft, admin_user):
    Employee.objects.create(
        company=draft.company,
        emp_code=draft.emp_code,
        name=draft.name,
        uan_number=draft.uan_number,
        esic_number=draft.esic_number,
    )

    draft.status = "APPROVED"
    draft.save()

    AuditLog.objects.create(
        action="EMPLOYEE_CREATED",
        performed_by=admin_user,
        description=f"Employee {draft.emp_code} approved"
    )