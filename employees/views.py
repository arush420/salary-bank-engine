from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
import pandas as pd
from django.template.defaulttags import now

from companies.models import Company
from payroll.models import SalaryTransaction
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from .forms import BankChangeRequestForm, EmployeeDraftForm
from .models import Employee, EmployeeDraft, AuditLog, EmployeeChangeRequest
from banking.models import EmployeeBankAccount, BankChangeRequest

from django.contrib.admin.views.decorators import staff_member_required
from django.utils import timezone




# @login_required
def request_bank_change(request, employee_id):
    if request.method == "POST":
        form = BankChangeRequestForm(request.POST)
        if form.is_valid():
            req = form.save(commit=False)
            req.employee_id = employee_id
            req.save()
            return redirect("employees:employee_profile", employee_id=employee_id)
    else:
        form = BankChangeRequestForm()

    return render(
        request,
        "employees/request_bank_change.html",
        {"form": form}
    )

def employee_list(request):
    employees = Employee.objects.order_by("emp_code")
    return render(
        request,
        "employees/employee_list.html",
        {"employees": employees}
    )


@login_required
def employee_profile(request, employee_id):
    employee = get_object_or_404(Employee, id=employee_id)

    # --------------------------
    # Handle Bank Change Submit
    # --------------------------
    if request.method == "POST":
        bank_form = BankChangeRequestForm(request.POST)

        if bank_form.is_valid():
            bank_request = bank_form.save(commit=False)
            bank_request.employee = employee
            bank_request.submitted_by = request.user   # ✅ FIXED
            bank_request.status = "PENDING"
            bank_request.save()

            messages.success(request, "Bank change request submitted for approval.")
            return redirect(request.path)
    else:
        bank_form = BankChangeRequestForm()

    # --------------------------
    # Existing Logic
    # --------------------------
    latest_salary = SalaryTransaction.objects.filter(
        employee=employee
    ).order_by("-created_at").first()

    bank_accounts = EmployeeBankAccount.objects.filter(
        employee=employee
    ).order_by("-is_active", "-approved_at")

    active_account = bank_accounts.filter(is_active=True).first()

    audit_logs = AuditLog.objects.filter(
        description__icontains=employee.emp_code
    ).order_by("-created_at")

    pending_changes = employee.change_requests.filter(status="PENDING")

    context = {
        "employee": employee,
        "latest_salary": latest_salary,
        "bank_accounts": bank_accounts,
        "active_account": active_account,
        "audit_logs": audit_logs,
        "pending_changes": pending_changes,
        "bank_form": bank_form,
    }

    return render(
        request,
        "employees/employee_profile.html",
        context
    )


@login_required
def employee_draft_create(request):
    if request.method == "POST":
        form = EmployeeDraftForm(request.POST)

        company_id = request.POST.get("company")
        if not company_id:
            messages.error(request, "Please select a company.")
            return redirect("employees:employee_draft_create")

        company = get_object_or_404(Company, id=company_id)

        if form.is_valid():
            draft = form.save(commit=False)
            draft.company = company          # 🔑 REQUIRED
            draft.created_by = request.user
            draft.status = "PENDING"
            draft.save()

            messages.success(
                request,
                "Employee draft submitted for approval."
            )
            return redirect("employees:employee_draft_list")
    else:
        form = EmployeeDraftForm()

    companies = Company.objects.order_by("name")

    return render(
        request,
        "employees/employee_draft_form.html",
        {
            "form": form,
            "companies": companies,
        }
    )



@login_required
def employee_draft_list(request):
    drafts = EmployeeDraft.objects.filter(status="PENDING").order_by("-created_at")
    return render(
        request,
        "employees/employee_draft_list.html",
        {"drafts": drafts}
    )

@login_required
def employee_draft_approval_list(request):
    drafts = EmployeeDraft.objects.filter(status="PENDING").select_related("company")

    draft_data = []

    for draft in drafts:
        conflicts = []
        merge_candidate = None

        # 🔴 HARD CONFLICT CHECKS
        if draft.esic_number and Employee.objects.filter(esic_number=draft.esic_number).exists():
            conflicts.append("ESIC already exists")

        if draft.uan_number and Employee.objects.filter(uan_number=draft.uan_number).exists():
            conflicts.append("UAN already exists")

        if draft.document_number and Employee.objects.filter(
            document_number=draft.document_number
        ).exists():
            conflicts.append("Document number already exists")

        if Employee.objects.filter(
            company=draft.company,
            emp_code=draft.emp_code
        ).exists():
            conflicts.append("Employee code already exists")

        # 🔁 MERGE CANDIDATE (ONLY IF CONFLICT EXISTS)
        if draft.esic_number:
            merge_candidate = Employee.objects.filter(
                esic_number=draft.esic_number
            ).first()

        if not merge_candidate and draft.uan_number:
            merge_candidate = Employee.objects.filter(
                uan_number=draft.uan_number
            ).first()

        draft_data.append({
            "draft": draft,
            "conflicts": conflicts,
            "can_approve": len(conflicts) == 0,
            "merge_candidate": merge_candidate,
        })

    return render(
        request,
        "employees/employee_draft_approval_list.html",
        {"draft_data": draft_data}
    )


from django.db import IntegrityError

@login_required
def approve_employee_draft(request, draft_id):
    draft = get_object_or_404(EmployeeDraft, id=draft_id, status="PENDING")

    # 🔎 Uniqueness checks
    conflicts = []

    if draft.esic_number and Employee.objects.filter(esic_number=draft.esic_number).exists():
        conflicts.append("ESIC number already exists")

    if draft.uan_number and Employee.objects.filter(uan_number=draft.uan_number).exists():
        conflicts.append("UAN number already exists")

    if draft.document_number and Employee.objects.filter(document_number=draft.document_number).exists():
        conflicts.append("Document number already exists")

    if conflicts:
        draft.status = "REJECTED"
        draft.save(update_fields=["status"])

        AuditLog.objects.create(
            action="EMPLOYEE_DRAFT_REJECTED",
            performed_by=request.user,
            description=(
                f"Draft {draft.emp_code} rejected due to conflicts: "
                + ", ".join(conflicts)
            )
        )

        messages.error(
            request,
            f"Draft rejected: {', '.join(conflicts)}"
        )
        return redirect("employees:employee_draft_approval_list")

    # ✅ Safe to create employee
    try:
        employee = Employee.objects.create(
            company=draft.company,
            emp_code=draft.emp_code,
            name=draft.name,
            father_name=draft.father_name,
            uan_number=draft.uan_number,
            esic_number=draft.esic_number,
            document_number=draft.document_number,
            default_salary=draft.default_salary,
            joining_date=draft.joining_date,
            approved_by=request.user,
        )
    except IntegrityError:
        messages.error(
            request,
            "Approval failed due to a uniqueness conflict."
        )
        return redirect("employees:employee_draft_approval_list")

    draft.status = "APPROVED"
    draft.save(update_fields=["status"])

    AuditLog.objects.create(
        action="EMPLOYEE_APPROVED",
        performed_by=request.user,
        description=f"Employee {employee.emp_code} approved from draft"
    )

    messages.success(request, f"Employee {employee.emp_code} approved successfully")
    return redirect("employees:employee_draft_approval_list")



@login_required
def reject_employee_draft(request, draft_id):
    draft = get_object_or_404(EmployeeDraft, id=draft_id, status="PENDING")

    draft.status = "REJECTED"
    draft.save(update_fields=["status"])

    AuditLog.objects.create(
        action="EMPLOYEE_REJECTED",
        performed_by=request.user,
        description=f"Employee draft {draft.emp_code} rejected"
    )

    messages.error(request, f"Employee draft {draft.emp_code} rejected")
    return redirect("employees:employee_draft_approval_list")



@login_required
def download_employee_draft_template(request):
    from companies.models import Company

    org = request.user.organisation_user.organisation

    # Get last draft within same organisation
    last = (
        EmployeeDraft.objects
        .filter(company__organisation=org)
        .order_by("-created_at")
        .first()
    )

    data = [{
        "site_code": last.company.site_code if last else "",
        "emp_code": last.emp_code if last else "",
        "name": last.name if last else "",
        "father_name": last.father_name if last else "",
        "joining_date": last.joining_date if last else "",
        "default_salary": last.default_salary if last else "",
        "uan_number": last.uan_number if last else "",
        "esic_number": last.esic_number if last else "",
        "document_number": last.document_number if last else "",
    }]

    df = pd.DataFrame(data)

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = "attachment; filename=employee_draft_template.xlsx"

    with pd.ExcelWriter(response, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Draft Template")

    return response


@login_required
def upload_employee_drafts(request):
    from companies.models import Company

    if request.method == "POST":
        file = request.FILES.get("file")

        if not file:
            messages.error(request, "Please upload a file")
            return redirect("employees:upload_employee_drafts")

        df = pd.read_excel(file)

        required_columns = {
            "site_code",
            "emp_code",
            "name",
            "father_name",
            "uan_number",
            "esic_number",
            "document_number",
            "default_salary",
            "joining_date",
        }

        if not required_columns.issubset(df.columns):
            messages.error(
                request,
                f"Excel must contain columns: {', '.join(sorted(required_columns))}"
            )
            return redirect("employees:upload_employee_drafts")

        org = request.user.organisation_user.organisation

        created = 0
        skipped = 0
        error_rows = []
        warning_rows = []

        with transaction.atomic():
            for index, row in df.iterrows():

                emp_code = str(row.get("emp_code", "")).strip()
                site_code = row.get("site_code")

                def skip(reason):
                    error_rows.append({
                        "row_number": index + 2,
                        "emp_code": emp_code or "—",
                        "reason": reason,
                    })

                if not emp_code:
                    skipped += 1
                    skip("Employee code missing")
                    continue

                # 🔹 Validate site_code
                try:
                    company = Company.objects.get(
                        site_code=int(site_code),
                        organisation=org
                    )
                except (Company.DoesNotExist, ValueError, TypeError):
                    skipped += 1
                    skip("Invalid site_code")
                    continue

                # Normalize identifiers
                esic = str(row.get("esic_number")).strip() if pd.notna(row.get("esic_number")) else None
                uan = str(row.get("uan_number")).strip() if pd.notna(row.get("uan_number")) else None
                doc = str(row.get("document_number")).strip() if pd.notna(row.get("document_number")) else None

                # 🔴 HARD BLOCKS
                if Employee.objects.filter(company=company, emp_code=emp_code).exists():
                    skipped += 1
                    skip("Employee code already exists in this company")
                    continue

                if esic and Employee.objects.filter(esic_number=esic).exists():
                    skipped += 1
                    skip("ESIC number already exists")
                    continue

                if uan and Employee.objects.filter(uan_number=uan).exists():
                    skipped += 1
                    skip("UAN number already exists")
                    continue

                if doc and Employee.objects.filter(document_number=doc).exists():
                    skipped += 1
                    skip("Document number already exists")
                    continue

                if EmployeeDraft.objects.filter(
                    company=company,
                    emp_code=emp_code,
                    status="PENDING"
                ).exists():
                    skipped += 1
                    skip("Pending draft already exists")
                    continue

                # Parse joining date
                joining_date = pd.to_datetime(row.get("joining_date"), errors="coerce")
                if pd.isna(joining_date):
                    skipped += 1
                    skip("Invalid joining date")
                    continue

                # 🟡 SOFT WARNINGS
                warnings = []

                if not row.get("father_name"):
                    warnings.append("Father name missing")

                salary = row.get("default_salary")
                if pd.isna(salary) or salary == "":
                    warnings.append("Default salary missing")
                elif isinstance(salary, (int, float)) and salary > 200000:
                    warnings.append("Unusually high salary")

                if Employee.objects.filter(
                    company=company,
                    name=str(row.get("name", "")).strip()
                ).exists():
                    warnings.append("Employee with same name exists in this company")

                # ✅ CREATE DRAFT
                EmployeeDraft.objects.create(
                    company=company,
                    emp_code=emp_code,
                    name=str(row.get("name", "")).strip(),
                    father_name=str(row.get("father_name", "")).strip(),
                    uan_number=uan,
                    esic_number=esic,
                    document_number=doc,
                    default_salary=salary,
                    joining_date=joining_date.date(),
                    created_by=request.user,
                )

                created += 1

                if warnings:
                    warning_rows.append({
                        "row_number": index + 2,
                        "emp_code": emp_code,
                        "warnings": warnings,
                    })

        # Store reports
        if error_rows:
            request.session["employee_draft_upload_errors"] = error_rows
            messages.warning(request, "Some rows were skipped.")
        else:
            request.session.pop("employee_draft_upload_errors", None)

        if warning_rows:
            request.session["employee_draft_upload_warnings"] = warning_rows
            messages.warning(request, f"{len(warning_rows)} drafts created with warnings.")
        else:
            request.session.pop("employee_draft_upload_warnings", None)

        messages.success(
            request,
            f"Upload completed: {created} drafts created, {skipped} rows skipped."
        )

        return redirect("employees:employee_draft_list")

    return render(request, "employees/employee_draft_upload.html")


@login_required
def preview_employee_drafts(request):
    preview = request.session.get("draft_upload_preview")
    return render(request, "employees/employee_draft_preview.html", {
        "preview": preview
    })

@login_required
def confirm_employee_drafts(request):
    preview = request.session.get("draft_upload_preview")
    # Save only rows with OK / WARNING


def request_employee_change(request, employee_id):
    employee = get_object_or_404(Employee, id=employee_id)

    if request.method == "POST":
        changes = {}

        for field in [
            "name",
            "father_name",
            "uan_number",
            "esic_number",
            "document_number",
            "default_salary",
            "exit_date",
        ]:
            new_val = request.POST.get(field)
            old_val = getattr(employee, field)

            if str(old_val) != str(new_val) and new_val:
                changes[field] = {
                    "old": old_val,
                    "new": new_val
                }

        if not changes:
            return redirect("employees:employee_profile", employee_id=employee.id)

        EmployeeChangeRequest.objects.create(
            employee=employee,
            changes=changes,
            requested_by=request.user
        )

        AuditLog.objects.create(
            action="EMPLOYEE_CHANGE_REQUESTED",
            description=f"Change requested for {employee.emp_code}: {changes}",
            performed_by=request.user
        )

        return redirect("employees:employee_profile", employee_id=employee.id)

    return render(
        request,
        "employees/employee_change_request.html",
        {"employee": employee, }
    )


def apply_employee_change(request, request_id):
    change_req = get_object_or_404(
        EmployeeChangeRequest,
        id=request_id,
        status="PENDING"
    )

    employee = change_req.employee

    for field, values in change_req.changes.items():
        setattr(employee, field, values["new"])

    employee.save()

    change_req.status = "APPLIED"
    change_req.applied_by = request.user
    change_req.applied_at = now()
    change_req.save()

    AuditLog.objects.create(
        action="EMPLOYEE_CHANGE_APPLIED",
        description=f"Applied changes to {employee.emp_code}: {change_req.changes}",
        performed_by=request.user
    )

    return redirect("employees:employee_profile", employee_id=employee.id)

@login_required
def approve_employee_change(request, employee_id):
    employee = get_object_or_404(Employee, id=employee_id)
    change_requests = employee.change_requests.filter(status="PENDING")

    if not change_requests.exists():
        return redirect("employees:employee_profile", employee.id)

    with transaction.atomic():
        for req in change_requests:
            for field, values in req.changes.items():
                setattr(employee, field, values["new"])  # ✅ FIXED

            employee.save()

            req.status = "APPROVED"
            req.reviewed_by = request.user
            req.reviewed_at = timezone.now()
            req.save()

            AuditLog.objects.create(
                action="EMPLOYEE_PROFILE_UPDATED",
                performed_by=request.user,
                description=(
                    f"Approved profile changes for "
                    f"{employee.emp_code}: {req.changes}"
                )
            )

    return redirect("employees:employee_profile", employee.id)@staff_member_required
def approve_employee_change(request, employee_id):
    employee = get_object_or_404(Employee, id=employee_id)
    change_requests = employee.change_requests.filter(status="PENDING")

    if not change_requests.exists():
        return redirect("employees:employee_profile", employee.id)

    with transaction.atomic():
        for req in change_requests:
            for field, values in req.changes.items():
                setattr(employee, field, values["new"])  # ✅ FIXED

            employee.save()

            req.status = "APPROVED"
            req.reviewed_by = request.user
            req.reviewed_at = timezone.now()
            req.save()

            AuditLog.objects.create(
                action="EMPLOYEE_PROFILE_UPDATED",
                performed_by=request.user,
                description=(
                    f"Approved profile changes for "
                    f"{employee.emp_code}: {req.changes}"
                )
            )

    return redirect("employees:employee_profile", employee.id)

@login_required
def reject_employee_change(request, employee_id):
    employee = get_object_or_404(Employee, id=employee_id)
    change_requests = employee.change_requests.filter(status="PENDING")

    with transaction.atomic():
        for req in change_requests:
            req.status = "REJECTED"
            req.reviewed_by = request.user
            req.reviewed_at = timezone.now()
            req.rejection_reason = "Rejected by admin"
            req.save()

            AuditLog.objects.create(
                action="EMPLOYEE_PROFILE_CHANGE_REJECTED",
                performed_by=request.user,
                description=(
                    f"Rejected profile change for "
                    f"{employee.emp_code}: {req.changes}"
                )
            )

    return redirect("employees:employee_profile", employee.id)


@login_required
def download_employee_draft_errors(request):
    errors = request.session.get("employee_draft_upload_errors")

    if not errors:
        messages.info(request, "No error report available.")
        return redirect("employees:employee_draft_list")

    df = pd.DataFrame(errors)

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = "attachment; filename=employee_draft_upload_errors.xlsx"

    df.to_excel(response, index=False)

    return response

@login_required
def merge_employee_draft(request, draft_id):
    draft = get_object_or_404(EmployeeDraft, id=draft_id, status="PENDING")

    # Find merge target (ESIC preferred, then UAN)
    employee = None
    if draft.esic_number:
        employee = Employee.objects.filter(esic_number=draft.esic_number).first()

    if not employee and draft.uan_number:
        employee = Employee.objects.filter(uan_number=draft.uan_number).first()

    if not employee:
        messages.error(request, "No matching employee found for merge.")
        return redirect("employees:employee_draft_approval_list")

    # 🔁 Merge only EMPTY fields on Employee
    merge_fields = [
        "father_name",
        "document_number",
        "default_salary",
        "exit_date",
    ]

    merged_fields = []

    for field in merge_fields:
        employee_value = getattr(employee, field, None)
        draft_value = getattr(draft, field, None)

        if not employee_value and draft_value:
            setattr(employee, field, draft_value)
            merged_fields.append(field)

    employee.save()

    # Mark draft as approved (merged)
    draft.status = "APPROVED"
    draft.save(update_fields=["status"])

    # Audit log
    AuditLog.objects.create(
        action="EMPLOYEE_DRAFT_MERGED",
        performed_by=request.user,
        description=(
            f"Draft {draft.emp_code} merged into "
            f"employee {employee.emp_code}. "
            f"Fields merged: {', '.join(merged_fields) or 'None'}"
        )
    )

    messages.success(
        request,
        f"Draft {draft.emp_code} merged into employee {employee.emp_code}."
    )

    return redirect("employees:employee_draft_approval_list")

@login_required
def delete_employee(request, employee_id):
    employee = get_object_or_404(Employee, id=employee_id)

    # HARD SAFETY CHECKS
    if SalaryTransaction.objects.filter(employee=employee).exists():
        messages.error(request, "Cannot delete employee with salary records.")
        return redirect("employees:employee_profile", employee.id)

    if EmployeeBankAccount.objects.filter(employee=employee).exists():
        messages.error(request, "Cannot delete employee with bank records.")
        return redirect("employees:employee_profile", employee.id)

    if request.method == "POST":
        AuditLog.objects.create(
            action="EMPLOYEE_DELETED",
            performed_by=request.user,
            description=f"Employee {employee.emp_code} deleted"
        )

        employee.delete()
        messages.success(request, "Employee deleted permanently.")
        return redirect("employees:employee_list")

    return redirect("employees:employee_profile", employee.id)
