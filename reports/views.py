from datetime import date
import calendar

import pandas as pd
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Sum, Count, Q
from django.urls import reverse

from companies.models import Company
from employees.models import Employee
from payroll.models import SalaryBatch, SalaryTransaction
from banking.models import BankChangeRequest, EmployeeBankAccount

MONTH_NAMES = {
    1:"January",2:"February",3:"March",4:"April",5:"May",6:"June",
    7:"July",8:"August",9:"September",10:"October",11:"November",12:"December",
}

def get_org(request):
    return request.user.organisation_user.organisation

def excel_response(filename):
    r = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    r["Content-Disposition"] = f'attachment; filename="{filename}"'
    return r

# ── DASHBOARD ──────────────────────────────────────────────────────────────────
@login_required
def reports_dashboard(request):
    return render(request, "reports/dashboard.html")

# ── 1. SALARY REGISTER ─────────────────────────────────────────────────────────
@login_required
def salary_report(request):
    today = date.today()
    org   = get_org(request)
    month      = int(request.GET.get("month", today.month))
    year       = int(request.GET.get("year",  today.year))
    company_id = request.GET.get("company")
    export     = request.GET.get("export")
    companies        = Company.objects.filter(organisation=org)
    selected_company = None
    transactions     = SalaryTransaction.objects.none()
    batch            = None
    totals           = {}
    if company_id:
        selected_company = get_object_or_404(Company, id=company_id, organisation=org)
        batch = SalaryBatch.objects.filter(company=selected_company, month=month, year=year).first()
        if batch:
            transactions = batch.transactions.select_related("employee","employee__company").order_by("employee__emp_code")
            totals = transactions.aggregate(total_salary=Sum("salary_amount"), total_count=Count("id"))
    if export == "excel" and selected_company and transactions.exists():
        rows = [{"Site Code":selected_company.site_code,"Company":selected_company.name,
            "Emp Code":t.employee.emp_code,"Employee Name":t.employee.name,
            "Father Name":t.employee.father_name,"UAN":t.employee.uan_number or "",
            "ESIC":t.employee.esic_number or "","Salary":t.salary_amount,
            "Account Number":t.account_number or "","IFSC":t.ifsc or "",
            "Status":t.status,"UTR":t.utr or "","Hold Reason":t.hold_reason or "",
        } for t in transactions]
        df = pd.DataFrame(rows)
        summary = df.groupby("Status")["Salary"].agg(Count="count",Total="sum").reset_index()
        summary.loc[len(summary)] = {"Status":"GRAND TOTAL","Count":summary["Count"].sum(),"Total":summary["Total"].sum()}
        resp = excel_response(f"{selected_company.name}_{month}_{year}_salary_register.xlsx")
        with pd.ExcelWriter(resp, engine="openpyxl") as w:
            df.to_excel(w, sheet_name="Salary Register", index=False)
            summary.to_excel(w, sheet_name="Summary", index=False)
        return resp
    return render(request, "reports/salary_report.html", {
        "companies":companies,"selected_company":selected_company,"transactions":transactions,
        "batch":batch,"totals":totals,"month":month,"year":year,"month_name":MONTH_NAMES[month],
        "months":range(1,13),"month_names":MONTH_NAMES,"years":range(today.year-3,today.year+2),
    })

# ── 2. MONTHLY HEADCOUNT ───────────────────────────────────────────────────────
@login_required
def headcount_report(request):
    today = date.today()
    org   = get_org(request)
    month      = int(request.GET.get("month", today.month))
    year       = int(request.GET.get("year",  today.year))
    company_id = request.GET.get("company")
    export     = request.GET.get("export")
    companies        = Company.objects.filter(organisation=org)
    selected_company = None
    rows             = []
    totals           = {}
    last_day = date(year, month, calendar.monthrange(year, month)[1])
    if company_id:
        selected_company = get_object_or_404(Company, id=company_id, organisation=org)
        employees = Employee.objects.filter(company=selected_company, joining_date__lte=last_day).select_related("company")
        active = employees.filter(Q(exit_date__isnull=True)|Q(exit_date__gt=last_day))
        exited = employees.filter(exit_date__lte=last_day)
        joined = employees.filter(joining_date__year=year, joining_date__month=month)
        left   = employees.filter(exit_date__year=year, exit_date__month=month)
        rows   = active.order_by("emp_code")
        totals = {"active":active.count(),"exited":exited.count(),"joined":joined.count(),"left":left.count()}
    if export == "excel" and selected_company and rows:
        df = pd.DataFrame([{"Emp Code":e.emp_code,"Name":e.name,"Father Name":e.father_name,
            "Company":e.company.name,"Joining Date":e.joining_date,"Exit Date":e.exit_date or "",
            "Status":"Active" if not e.exit_date else "Exited","UAN":e.uan_number or "","ESIC":e.esic_number or "",
        } for e in rows])
        summary = pd.DataFrame([{"Active Employees":totals["active"],"Joined This Month":totals["joined"],"Left This Month":totals["left"]}])
        resp = excel_response(f"{selected_company.name}_{MONTH_NAMES[month]}_{year}_headcount.xlsx")
        with pd.ExcelWriter(resp, engine="openpyxl") as w:
            df.to_excel(w, sheet_name="Headcount", index=False)
            summary.to_excel(w, sheet_name="Summary", index=False)
        return resp
    return render(request, "reports/headcount_report.html", {
        "companies":companies,"selected_company":selected_company,"rows":rows,"totals":totals,
        "month":month,"year":year,"month_name":MONTH_NAMES[month],
        "months":range(1,13),"month_names":MONTH_NAMES,"years":range(today.year-3,today.year+2),
    })

# ── 3. JOINING & EXIT REPORT ───────────────────────────────────────────────────
@login_required
def joining_exit_report(request):
    org         = get_org(request)
    company_id  = request.GET.get("company")
    from_date   = request.GET.get("from_date")
    to_date     = request.GET.get("to_date")
    report_type = request.GET.get("report_type", "both")
    export      = request.GET.get("export")
    companies        = Company.objects.filter(organisation=org)
    selected_company = None
    joined_qs        = Employee.objects.none()
    exited_qs        = Employee.objects.none()
    if company_id and from_date and to_date:
        selected_company = get_object_or_404(Company, id=company_id, organisation=org)
        base = Employee.objects.filter(company=selected_company).select_related("company")
        if report_type in ("joining","both"):
            joined_qs = base.filter(joining_date__range=[from_date,to_date]).order_by("joining_date")
        if report_type in ("exit","both"):
            exited_qs = base.filter(exit_date__range=[from_date,to_date]).order_by("exit_date")
    if export == "excel" and selected_company:
        dfs = {}
        if joined_qs.exists():
            dfs["Joinings"] = pd.DataFrame([{"Emp Code":e.emp_code,"Name":e.name,
                "Father Name":e.father_name,"Joining Date":e.joining_date,
                "UAN":e.uan_number or "","ESIC":e.esic_number or ""} for e in joined_qs])
        if exited_qs.exists():
            dfs["Exits"] = pd.DataFrame([{"Emp Code":e.emp_code,"Name":e.name,
                "Father Name":e.father_name,"Joining Date":e.joining_date,"Exit Date":e.exit_date,
                "UAN":e.uan_number or "","ESIC":e.esic_number or ""} for e in exited_qs])
        if not dfs:
            messages.warning(request, "No data found for selected filters.")
            return redirect(request.path+f"?company={company_id}&from_date={from_date}&to_date={to_date}&report_type={report_type}")
        resp = excel_response(f"{selected_company.name}_{from_date}_{to_date}_joining_exit.xlsx")
        with pd.ExcelWriter(resp, engine="openpyxl") as w:
            for name, df in dfs.items():
                df.to_excel(w, sheet_name=name, index=False)
        return resp
    return render(request, "reports/joining_exit_report.html", {
        "companies":companies,"selected_company":selected_company,
        "joined_qs":joined_qs,"exited_qs":exited_qs,
        "from_date":from_date or "","to_date":to_date or "","report_type":report_type,
    })

# ── 4. BANK DISBURSEMENT ───────────────────────────────────────────────────────
@login_required
def bank_disbursement_report(request):
    today = date.today()
    org   = get_org(request)
    month      = int(request.GET.get("month", today.month))
    year       = int(request.GET.get("year",  today.year))
    company_id = request.GET.get("company")
    export     = request.GET.get("export")
    companies        = Company.objects.filter(organisation=org)
    selected_company = None
    transactions     = SalaryTransaction.objects.none()
    batch            = None
    totals           = {}
    if company_id:
        selected_company = get_object_or_404(Company, id=company_id, organisation=org)
        batch = SalaryBatch.objects.filter(company=selected_company, month=month, year=year).first()
        if batch:
            transactions = batch.transactions.select_related("employee").order_by("employee__emp_code")
            totals = {
                "total":     transactions.aggregate(s=Sum("salary_amount"))["s"] or 0,
                "completed": transactions.filter(status="COMPLETED").aggregate(s=Sum("salary_amount"))["s"] or 0,
                "pending":   transactions.filter(status__in=["PENDING","READY"]).aggregate(s=Sum("salary_amount"))["s"] or 0,
                "hold":      transactions.filter(status="HOLD").aggregate(s=Sum("salary_amount"))["s"] or 0,
                "failed":    transactions.filter(status="FAILED").aggregate(s=Sum("salary_amount"))["s"] or 0,
                "count":     transactions.count(),
            }
    if export == "excel" and selected_company and transactions.exists():
        df = pd.DataFrame([{"Emp Code":t.employee.emp_code,"Employee Name":t.employee.name,
            "Account Number":t.account_number or "","IFSC":t.ifsc or "",
            "Salary Amount":t.salary_amount,"Status":t.status,"UTR":t.utr or "",
            "Bank Response":t.bank_response_at.strftime("%d-%m-%Y %H:%M") if t.bank_response_at else "",
            "Hold Reason":t.hold_reason or "","Failure Reason":t.failure_reason or "",
        } for t in transactions])
        summary = df.groupby("Status")["Salary Amount"].agg(Employees="count",Total="sum").reset_index()
        resp = excel_response(f"{selected_company.name}_{month}_{year}_bank_disbursement.xlsx")
        with pd.ExcelWriter(resp, engine="openpyxl") as w:
            df.to_excel(w, sheet_name="Disbursement", index=False)
            summary.to_excel(w, sheet_name="Status Summary", index=False)
        return resp
    return render(request, "reports/bank_disbursement_report.html", {
        "companies":companies,"selected_company":selected_company,"transactions":transactions,
        "batch":batch,"totals":totals,"month":month,"year":year,"month_name":MONTH_NAMES[month],
        "months":range(1,13),"month_names":MONTH_NAMES,"years":range(today.year-3,today.year+2),
    })

# ── 5. PF / ESIC CONTRIBUTION ─────────────────────────────────────────────────
@login_required
def pf_esic_report(request):
    today = date.today()
    org   = get_org(request)
    month      = int(request.GET.get("month", today.month))
    year       = int(request.GET.get("year",  today.year))
    company_id = request.GET.get("company")
    export     = request.GET.get("export")
    PF_RATE    = 0.12
    ESIC_RATE  = 0.0075
    ER_ESIC    = 0.0325
    companies        = Company.objects.filter(organisation=org)
    selected_company = None
    transactions     = SalaryTransaction.objects.none()
    totals           = {}
    if company_id:
        selected_company = get_object_or_404(Company, id=company_id, organisation=org)
        batch = SalaryBatch.objects.filter(company=selected_company, month=month, year=year).first()
        if batch:
            qs = batch.transactions.select_related("employee").filter(
                status__in=["COMPLETED","PROCESSED","EXPORTED","READY"]
            ).order_by("employee__emp_code")
            # Annotate each transaction with calculated PF/ESIC for template display
            annotated = []
            for t in qs:
                s = float(t.salary_amount)
                t.employee_pf   = round(s * PF_RATE,   2)
                t.employer_pf   = round(s * PF_RATE,   2)
                t.total_pf      = round(s * PF_RATE * 2, 2)
                t.employee_esic = round(s * ESIC_RATE, 2)
                t.employer_esic = round(s * ER_ESIC,   2)
                t.total_esic    = round(s * (ESIC_RATE + ER_ESIC), 2)
                annotated.append(t)
            transactions = annotated
            total_salary = float(qs.aggregate(s=Sum("salary_amount"))["s"] or 0)
            totals = {
                "total_salary":   total_salary,
                "employee_pf":    round(total_salary * PF_RATE, 2),
                "employer_pf":    round(total_salary * PF_RATE, 2),
                "employee_esic":  round(total_salary * ESIC_RATE, 2),
                "employer_esic":  round(total_salary * ER_ESIC, 2),
                "count":          len(annotated),
            }
    if export == "excel" and selected_company and transactions:
        rows = []
        for t in transactions:
            s = float(t.salary_amount)
            rows.append({"Emp Code":t.employee.emp_code,"Employee Name":t.employee.name,
                "UAN":t.employee.uan_number or "","ESIC Number":t.employee.esic_number or "",
                "Gross Salary":s,
                "Employee PF (12%)":round(s*PF_RATE,2),"Employer PF (12%)":round(s*PF_RATE,2),
                "Employee ESIC (0.75%)":round(s*ESIC_RATE,2),"Employer ESIC (3.25%)":round(s*ER_ESIC,2),
                "Total PF":round(s*PF_RATE*2,2),"Total ESIC":round(s*(ESIC_RATE+ER_ESIC),2),
            })
        df = pd.DataFrame(rows)
        total_row = {c: df[c].sum() if df[c].dtype != object else ("TOTAL" if c=="Emp Code" else "") for c in df.columns}
        df = pd.concat([df, pd.DataFrame([total_row])], ignore_index=True)
        resp = excel_response(f"{selected_company.name}_{month}_{year}_pf_esic.xlsx")
        with pd.ExcelWriter(resp, engine="openpyxl") as w:
            df.to_excel(w, sheet_name="PF ESIC Report", index=False)
        return resp
    return render(request, "reports/pf_esic_report.html", {
        "companies":companies,"selected_company":selected_company,"transactions":transactions,
        "totals":totals,"month":month,"year":year,"month_name":MONTH_NAMES[month],
        "months":range(1,13),"month_names":MONTH_NAMES,"years":range(today.year-3,today.year+2),
        "PF_RATE":PF_RATE,"ESIC_RATE":ESIC_RATE,"ER_ESIC":ER_ESIC,
    })

# ── EXISTING VIEWS ─────────────────────────────────────────────────────────────
@login_required
def yearly_salary_report(request):
    year=request.GET.get("year"); company_id=request.GET.get("company")
    if not year or not company_id: return HttpResponse("Year and Company required")
    org=get_org(request); company=get_object_or_404(Company,id=company_id,organisation=org)
    batches=SalaryBatch.objects.filter(company=company,year=year)
    transactions=SalaryTransaction.objects.filter(batch__in=batches).select_related("employee","batch")
    if not transactions.exists(): return HttpResponse("No salary data for selected year")
    detail_rows=[{"Month":t.batch.month,"Emp Code":t.employee.emp_code,"Employee Name":t.employee.name,"Salary":t.salary_amount,"Status":t.status} for t in transactions]
    df_detail=pd.DataFrame(detail_rows)
    monthly_summary=df_detail.groupby(["Month","Status"])["Salary"].agg(["count","sum"]).reset_index()
    monthly_pivot=monthly_summary.pivot_table(index="Month",columns="Status",values="sum",fill_value=0).reset_index()
    monthly_total=df_detail.groupby("Month")["Salary"].sum().reset_index(name="Total Salary")
    df_monthly=monthly_total.merge(monthly_pivot,on="Month",how="left")
    df_year=pd.DataFrame([{"Total Transactions":len(df_detail),"Total Salary":df_detail["Salary"].sum(),
        "Processed Salary":df_detail[df_detail["Status"]=="PROCESSED"]["Salary"].sum(),
        "Hold Salary":df_detail[df_detail["Status"]=="HOLD"]["Salary"].sum(),
        "Failed Salary":df_detail[df_detail["Status"]=="FAILED"]["Salary"].sum()}])
    resp=excel_response(f"{company.name}_{year}_yearly_salary_report.xlsx")
    with pd.ExcelWriter(resp,engine="openpyxl") as w:
        df_detail.to_excel(w,sheet_name="Transactions",index=False)
        df_monthly.to_excel(w,sheet_name="Monthly Summary",index=False)
        df_year.to_excel(w,sheet_name="Year Summary",index=False)
    return resp

@login_required
def bank_change_report(request):
    today      = date.today()
    org        = get_org(request)
    month      = request.GET.get("month", "")
    year       = request.GET.get("year", str(today.year))
    status     = request.GET.get("status", "ALL")
    company_id = request.GET.get("company", "")
    export     = request.GET.get("export")

    companies = Company.objects.filter(organisation=org)

    qs = BankChangeRequest.objects.select_related(
        "employee", "submitted_by", "approved_by", "employee__company"
    ).filter(employee__company__organisation=org).order_by("-id")

    if company_id:
        qs = qs.filter(employee__company__id=company_id)
    if month:
        qs = qs.filter(effective_month=month)
    if year:
        qs = qs.filter(effective_year=year)
    if status and status != "ALL":
        qs = qs.filter(status=status)

    if export == "excel":
        cols = ["Company","Emp Code","Employee Name","New Bank","New Account","IFSC","Effective Month","Effective Year","Status","Submitted By","Approved By"]
        rows = [{"Company":r.employee.company.name,"Emp Code":r.employee.emp_code,
            "Employee Name":r.employee.name,"New Bank":r.new_bank_name,
            "New Account":r.new_account_number,"IFSC":r.new_ifsc,
            "Effective Month":r.effective_month,"Effective Year":r.effective_year,
            "Status":r.status,"Submitted By":r.submitted_by.username,
            "Approved By":r.approved_by.username if r.approved_by else ""} for r in qs]
        df   = pd.DataFrame(rows) if rows else pd.DataFrame(columns=cols)
        resp = excel_response("bank_change_report.xlsx")
        df.to_excel(resp, index=False)
        return resp

    return render(request, "reports/bank_change_report.html", {
        "companies":      companies,
        "requests":       qs,
        "month":          month,
        "year":           year,
        "status":         status,
        "company_id":     company_id,
        "status_choices": ["ALL", "PENDING", "APPROVED", "REJECTED"],
        "years":          range(today.year - 3, today.year + 2),
    })

@login_required
def transaction_status_manager(request):
    today=date.today(); org=get_org(request)
    month=int(request.GET.get("month",today.month)); year=int(request.GET.get("year",today.year))
    company_id=request.GET.get("company"); status_filter=request.GET.get("status","ALL")
    companies=Company.objects.filter(organisation=org)
    selected_company=None; transactions=SalaryTransaction.objects.none(); batch=None; summary={}
    if request.method=="POST":
        action=request.POST.get("action"); transaction_id=request.POST.get("transaction_id")
        hold_reason=request.POST.get("hold_reason","").strip()
        txn=get_object_or_404(SalaryTransaction,id=transaction_id)
        if action=="hold":
            if not hold_reason: messages.error(request,"Please provide a reason for holding.")
            else:
                txn.status="HOLD"; txn.hold_reason=hold_reason; txn.save()
                messages.success(request,f"{txn.employee.name} salary placed on hold.")
        elif action=="unhold":
            txn.status="PENDING"; txn.hold_reason=None; txn.save()
            messages.success(request,f"Hold removed for {txn.employee.name}.")
        elif action=="mark_ready":
            if txn.status=="PENDING":
                txn.status="READY"; txn.save()
                messages.success(request,f"{txn.employee.name} marked as Ready for Export.")
        return redirect(request.path+f"?month={month}&year={year}&company={company_id or ''}&status={status_filter}")
    if company_id:
        selected_company=get_object_or_404(Company,id=company_id,organisation=org)
        batch=SalaryBatch.objects.filter(company=selected_company,month=month,year=year).first()
        if batch:
            all_txns=batch.transactions.select_related("employee")
            transactions=all_txns.filter(status=status_filter) if status_filter!="ALL" else all_txns
            summary={"PENDING":all_txns.filter(status="PENDING").count(),"HOLD":all_txns.filter(status="HOLD").count(),
                "READY":all_txns.filter(status="READY").count(),"EXPORTED":all_txns.filter(status="EXPORTED").count(),
                "COMPLETED":all_txns.filter(status="COMPLETED").count()}
    return render(request,"reports/transaction_status_manager.html",{
        "companies":companies,"selected_company":selected_company,"transactions":transactions,
        "month":month,"year":year,"months":range(1,13),"years":range(today.year-3,today.year+2),
        "status_filter":status_filter,"summary":summary,
    })

@login_required
def reprocess_bank_snapshot(request):
    if request.method!="POST": return redirect("reports:salary_report")
    company_id=request.POST.get("company"); month=request.POST.get("month"); year=request.POST.get("year")
    org=get_org(request); company=get_object_or_404(Company,id=company_id,organisation=org)
    batch=get_object_or_404(SalaryBatch,company=company,month=month,year=year)
    updated=skipped=0
    for txn in SalaryTransaction.objects.filter(batch=batch).select_related("employee"):
        active_bank=EmployeeBankAccount.objects.filter(employee=txn.employee,is_active=True).first()
        if active_bank:
            txn.account_number=active_bank.account_number; txn.ifsc=active_bank.ifsc
            txn.save(update_fields=["account_number","ifsc"]); updated+=1
        else: skipped+=1
    messages.success(request,f"Reprocessed {updated} transactions. {skipped} skipped (no active bank).")
    return redirect(f"{reverse('reports:salary_report')}?company={company_id}&month={month}&year={year}")
