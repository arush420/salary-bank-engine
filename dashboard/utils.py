def can_reverse_batch(user):
    return user.is_superuser or user.groups.filter(name="PAYROLL_ADMIN").exists()
