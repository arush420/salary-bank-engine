from banking.models import EmployeeBankAccount


def should_hold_salary(employee):
    """
    Returns (True, reason) if salary must be put on HOLD
    """

    if not employee.is_active:
        return True, "Employee is inactive / left"

    active_bank = EmployeeBankAccount.objects.filter(
        employee=employee,
        is_active=True
    ).first()

    if not active_bank:
        return True, "No active bank account"

    return False, None
