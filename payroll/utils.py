from banking.models import EmployeeBankAccount
from payroll.models import SalaryTransaction


def should_hold_salary(employee):
    """
    Returns (True, reason) if salary must be put on HOLD
    """

    if employee.exit_date:
        return True, "Employee has exited"

    active_bank = EmployeeBankAccount.objects.filter(
        employee=employee,
        is_active=True
    ).first()

    if not active_bank:
        return True, "No active bank account"

    return False, None


def release_salary_holds(employee):
    """
    Release all HOLD salaries for an employee
    once bank account becomes active
    """
    qs = SalaryTransaction.objects.filter(
        employee=employee,
        status="HOLD"
    )

    for txn in qs:
        txn.status = "PENDING"
        txn.hold_reason = None
        txn.save(update_fields=["status", "hold_reason"])


def assert_batch_not_reversed(batch):
    if batch.status == "REVERSED":
        raise Exception("Batch reversed")
