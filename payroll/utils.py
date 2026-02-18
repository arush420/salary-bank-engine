from banking.models import EmployeeBankAccount, BankChangeRequest
from employees.models import EmployeeChangeRequest
from payroll.models import SalaryTransaction
from datetime import date


def should_hold_salary(employee, batch_month=None, batch_year=None):
    """
    Returns (True, reason) if salary must be put on HOLD
    """

    # ------------------------------------------------
    # 1️⃣ Employee exited
    # ------------------------------------------------
    if employee.exit_date:
        return True, "Employee has exited"

    # ------------------------------------------------
    # 2️⃣ Future joining date
    # ------------------------------------------------
    today = date.today()
    if employee.joining_date > today:
        return True, "Employee joining date is in future"

    # ------------------------------------------------
    # 3️⃣ Joined after payroll month
    # ------------------------------------------------
    if batch_month and batch_year:
        payroll_date = date(batch_year, batch_month, 1)

        if employee.joining_date > payroll_date:
            return True, "Employee joined after payroll month"

    # ------------------------------------------------
    # 4️⃣ Pending profile change
    # ------------------------------------------------
    if EmployeeChangeRequest.objects.filter(
        employee=employee,
        status="PENDING"
    ).exists():
        return True, "Pending profile change request"

    # ------------------------------------------------
    # 5️⃣ Pending bank change
    # ------------------------------------------------
    if BankChangeRequest.objects.filter(
        employee=employee,
        status="PENDING"
    ).exists():
        return True, "Pending bank change request"

    # ------------------------------------------------
    # 6️⃣ No active bank account
    # ------------------------------------------------
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
